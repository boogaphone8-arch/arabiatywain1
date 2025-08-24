from flask import render_template, request, redirect, url_for, session, flash
from app import app, db, ADMIN_PASSWORD, OWNER_PHONE, OWNER_WHATSAPP
from models import Report, Match
from utils import normalize_plate, normalize_chassis, save_image, find_matches_for

def is_admin() -> bool:
    """Check if current user is admin"""
    return session.get("is_admin") is True

@app.route("/")
def home():
    """Home page with statistics"""
    # Get statistics
    total_lost = Report.query.filter_by(report_type="lost", is_active=True).count()
    total_sightings = Report.query.filter_by(report_type="sighting", is_active=True).count()
    total_matches = Match.query.count()
    
    stats = {
        'lost_reports': total_lost,
        'sighting_reports': total_sightings,
        'total_reports': total_lost + total_sightings,
        'matches_found': total_matches
    }
    
    return render_template("index.html", stats=stats)

@app.route("/contact")
def contact():
    """Contact page with mediator information"""
    return render_template(
        "contact.html", 
        owner_phone=OWNER_PHONE, 
        owner_whatsapp=OWNER_WHATSAPP
    )

@app.route("/search", methods=["GET", "POST"])
def search():
    """Search for cars by plate or chassis number"""
    status = None
    results = []
    query_value = ""
    mode = "plate"
    
    if request.method == "POST":
        mode = request.form.get("mode")  # plate or chassis
        query_value = request.form.get("value", "").strip()
        
        if not query_value:
            flash("يرجى إدخال قيمة للبحث", "error")
            return render_template("search.html", status=status, results=results, query_value=query_value, mode=mode)
        
        key = normalize_plate(query_value) if mode == "plate" else normalize_chassis(query_value)

        # Check if car is reported as lost
        lost_q = Report.query.filter_by(report_type="lost", is_active=True)
        lost = (lost_q.filter(Report.plate == key).all() if mode == "plate"
                else lost_q.filter(Report.chassis == key).all())
        
        status = "raised" if lost else "clear"

        # Check for matches between lost and sighting reports
        related = Report.query.filter(
            (Report.plate == key) if mode == "plate" else (Report.chassis == key)
        ).all()
        
        match_rows = []
        for r in related:
            if r.report_type == "lost":
                matches = Match.query.filter_by(lost_id=r.id).all()
            else:
                matches = Match.query.filter_by(sighting_id=r.id).all()
            match_rows.extend(matches)
        
        # Remove duplicates
        unique_matches = {}
        for m in match_rows:
            unique_matches[(m.lost_id, m.sighting_id, m.rule)] = m
        match_rows = list(unique_matches.values())
        
        if match_rows:
            status = "matched"
            for m in match_rows:
                lost_r = Report.query.get(m.lost_id)
                sight_r = Report.query.get(m.sighting_id)
                results.append({
                    "rule": m.rule, 
                    "lost": lost_r, 
                    "sighting": sight_r,
                    "mediator_phone": OWNER_PHONE,
                    "mediator_whatsapp": OWNER_WHATSAPP
                })

    return render_template(
        "search.html", 
        status=status, 
        results=results, 
        query_value=query_value, 
        mode=mode
    )

@app.route("/report/<rtype>", methods=["GET", "POST"])
def make_report(rtype):
    """Create a new report (lost or sighting)"""
    if rtype not in ("lost", "sighting"):
        return redirect(url_for("home"))
    
    if request.method == "POST":
        car_name = request.form.get("car_name", "").strip()
        model = request.form.get("model", "").strip()
        color = request.form.get("color", "").strip()
        chassis = normalize_chassis(request.form.get("chassis", "").strip())
        plate = normalize_plate(request.form.get("plate", "").strip())
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()
        notes = request.form.get("notes", "").strip()
        image_file = request.files.get("image")

        # Validation
        if not car_name or not phone or (not chassis and not plate):
            flash("لازم اسم العربية ورقم هاتف وواحد على الأقل من الشاسي أو اللوحة.", "error")
            return redirect(request.url)

        # Save image if provided
        image_path = save_image(image_file)

        # Create new report
        new_report = Report()
        new_report.report_type = rtype
        new_report.car_name = car_name
        new_report.model = model or None
        new_report.color = color or None
        new_report.chassis = chassis or None
        new_report.plate = plate or None
        new_report.location = location or None
        new_report.phone = phone
        new_report.image_path = image_path
        new_report.notes = notes or None
        
        db.session.add(new_report)
        db.session.commit()

        # Look for matches
        matches = find_matches_for(new_report)
        
        if matches:
            flash("تم تسجيل البلاغ ووجدنا تطابقاً. تواصل مع الوسيط لإكمال الإجراءات.", "success")
        else:
            if rtype == "lost":
                flash("تم تسجيل بلاغ الفقدان بنجاح. سننبه عند ظهور رصد مطابق.", "success")
            else:
                flash("تم تسجيل بلاغ الرصد. لو في فقدان مطابق لاحقاً، سيظهر في نتائج البحث.", "success")

        return redirect(url_for("home"))
    
    return render_template("report_form.html", rtype=rtype)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page"""
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("كلمة المرور غير صحيحة.", "error")
    
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    """Admin logout"""
    session.pop("is_admin", None)
    return redirect(url_for("home"))

@app.route("/admin")
def admin_dashboard():
    """Admin dashboard showing reports and matches"""
    if not is_admin():
        return redirect(url_for("admin_login"))
    
    # Get latest reports
    latest_reports = Report.query.order_by(Report.created_at.desc()).limit(50).all()
    
    # Get latest matches with related reports
    latest_matches = Match.query.order_by(Match.created_at.desc()).limit(50).all()
    matches_view = []
    
    for m in latest_matches:
        lost_r = Report.query.get(m.lost_id)
        sight_r = Report.query.get(m.sighting_id)
        matches_view.append({
            "m": m, 
            "lost": lost_r, 
            "sighting": sight_r
        })
    
    return render_template(
        "admin.html", 
        reports=latest_reports, 
        matches=matches_view
    )

@app.route("/admin/bulk-import", methods=["GET", "POST"])
def bulk_import():
    """Bulk import reports from text data"""
    if not is_admin():
        return redirect(url_for("admin_login"))
    
    if request.method == "POST":
        bulk_data = request.form.get("bulk_data", "").strip()
        
        if not bulk_data:
            flash("يرجى إدخال البيانات", "warning")
            return render_template("bulk_import.html")
        
        from utils import process_bulk_data
        results = process_bulk_data(bulk_data)
        return render_template("bulk_import.html", results=results)
    
    return render_template("bulk_import.html")
