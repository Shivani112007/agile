"""SYNORA - Cloud-Based Student Skill Portfolio & Opportunity Matching System.
Polished Flask UI using the existing in-memory/DynamoDB store and application routes.
"""
import os, uuid
from datetime import date
from flask import (
    Flask, request, session, redirect, url_for,
    render_template_string, jsonify, flash, abort
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from botocore.exceptions import ClientError

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@portal.com").lower()
S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    "pdf", "docx", "jpg", "jpeg", "png"
}

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
TABLES = ("students", "opportunities", "applications")


class Store:
    """In-memory by default; DynamoDB when USE_DYNAMODB=1."""
    def __init__(self):
        self.mem = {t: {} for t in TABLES}
        self.ddb = None
        if os.getenv("USE_DYNAMODB") == "1":
            import boto3
            self.ddb = boto3.resource(
                "dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1")
            )

    def _t(self, t):
        return self.ddb.Table(f"SkillPortal-{t}")

    def put(self, t, item):
        if self.ddb:
            self._t(t).put_item(Item=item)
        else:
            self.mem[t][item["id"]] = item

    def get(self, t, key):
        if self.ddb:
            return self._t(t).get_item(Key={"id": key}).get("Item")
        return self.mem[t].get(key)

    def all(self, t):
        return self._t(t).scan().get("Items", []) if self.ddb else list(self.mem[t].values())


db = Store()


def split(text):
    return [s.strip() for s in (text or "").replace("\n", ",").split(",") if s.strip()]


def match_score(student_skills, required_skills):
    """Percentage of required skills the student has (case-insensitive)."""
    req = {s.strip().lower() for s in required_skills if s.strip()}
    if not req:
        return 0
    have = {s.strip().lower() for s in student_skills if s.strip()}
    return round(100 * len(req & have) / len(req))


def me():
    return db.get("students", session["user"]) if "user" in session else None


def ensure_profile_fields(u):
    """Backwards-compatible defaults for records created by the original version."""
    for field in ("skills", "projects", "certificates", "interests", "achievements", "education"):
        u.setdefault(field, [])
    return u


def profile_completion(u):
    ensure_profile_fields(u)
    checks = [
        bool(u.get("name")),
        bool(u.get("skills")),
        bool(u.get("projects")),
        bool(u.get("certificates")),
        bool(u.get("achievements")),
        bool(u.get("interests")),
        bool(u.get("education")),
    ]
    return round(sum(checks) * 100 / len(checks))


CSS = r"""
:root {
  --ink:#182033; --muted:#687089; --line:#e8eaf1; --surface:#fff; --bg:#f6f7fb;
  --brand:#635bff; --brand2:#8b5cf6; --teal:#14b8a6; --green:#16a34a;
  --danger:#dc2626; --shadow:0 18px 50px rgba(31,35,58,.08);
}
*{box-sizing:border-box} html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:inherit;text-decoration:none}.container{width:min(1180px,calc(100% - 36px));margin:auto}
.nav{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.86);backdrop-filter:blur(16px);border-bottom:1px solid rgba(232,234,241,.8)}
.nav-in{height:72px;display:flex;align-items:center;gap:26px}.brand{display:flex;align-items:center;gap:10px;font-weight:900;font-size:20px;letter-spacing:-.04em}
.logo{width:36px;height:36px;border-radius:12px;background:linear-gradient(135deg,var(--brand),var(--brand2));display:grid;place-items:center;color:#fff;box-shadow:0 8px 20px rgba(99,91,255,.25)}
.logo:after{content:"S";font-weight:900}.navlinks{display:flex;align-items:center;gap:5px;margin-left:auto}.navlinks a{padding:9px 12px;border-radius:10px;color:#687089;font-size:14px;font-weight:700}.navlinks a:hover{background:#f0f0ff;color:var(--brand)}
.user-pill{display:flex;align-items:center;gap:8px;padding:6px 10px 6px 6px;background:#f4f5f9;border-radius:99px;font-size:13px;font-weight:700}.avatar{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:#dedcff;color:#5149db}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:0;border-radius:12px;padding:11px 16px;font-weight:800;font-size:14px;cursor:pointer;transition:.2s;line-height:1}.btn:hover{transform:translateY(-1px)}.btn-primary{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;box-shadow:0 10px 22px rgba(99,91,255,.2)}.btn-soft{background:#f0f0ff;color:#5149db}.btn-dark{background:#182033;color:#fff}.btn-danger{background:#fee2e2;color:#b91c1c}.btn-sm{padding:8px 11px;font-size:12px;border-radius:9px}
.hero{padding:82px 0 70px;background:radial-gradient(circle at 15% 10%,#e9e7ff 0,transparent 34%),radial-gradient(circle at 88% 15%,#ddfbf6 0,transparent 30%),#f7f7fc}
.hero-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:54px;align-items:center}.eyebrow{display:inline-flex;padding:7px 10px;border-radius:99px;background:#eeedff;color:#554dd8;font-size:12px;font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.hero h1{font-size:clamp(42px,6vw,72px);line-height:.98;letter-spacing:-.065em;margin:18px 0}.gradient{background:linear-gradient(110deg,var(--brand),#9b5cff 45%,#0ea5a0);-webkit-background-clip:text;background-clip:text;color:transparent}.hero p{font-size:18px;line-height:1.7;color:var(--muted);max-width:650px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}.hero-card{background:#fff;border:1px solid var(--line);border-radius:28px;padding:24px;box-shadow:var(--shadow);transform:rotate(1deg)}
.mock-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.mock-label{font-size:12px;color:var(--muted);font-weight:800}.score{font-size:28px;font-weight:900;color:var(--brand)}.progress{height:8px;background:#eeeef5;border-radius:99px;overflow:hidden}.progress i{display:block;height:100%;background:linear-gradient(90deg,var(--brand),var(--teal));border-radius:inherit}.mini-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px}.mini{border:1px solid var(--line);border-radius:14px;padding:14px}.mini b{display:block;margin-bottom:5px}.mini span{font-size:12px;color:var(--muted)}
.section{padding:70px 0}.section-head{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:25px}.section h2{font-size:34px;letter-spacing:-.045em;margin:0 0 8px}.section-head p{margin:0;color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.feature{background:#fff;border:1px solid var(--line);border-radius:20px;padding:24px;box-shadow:0 8px 30px rgba(31,35,58,.04)}.feature-icon{width:44px;height:44px;border-radius:13px;background:#f0f0ff;color:var(--brand);display:grid;place-items:center;font-weight:900;margin-bottom:18px}.feature h3{margin:0 0 8px}.feature p{color:var(--muted);line-height:1.65;margin:0}
.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.step{padding:20px;border:1px dashed #d7d8e5;border-radius:18px}.num{font-weight:900;color:var(--brand);font-size:13px}.step h3{margin:9px 0 6px}.step p{color:var(--muted);font-size:14px;line-height:1.55;margin:0}
.cta{margin-top:15px;border-radius:28px;padding:42px;background:linear-gradient(120deg,#181b2c,#35305c);color:#fff;display:flex;align-items:center;justify-content:space-between;gap:30px}.cta p{color:#c9c9d8;margin-bottom:0}
.page{padding:38px 0 70px}.page-title{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:25px}.page-title h1{margin:0;font-size:34px;letter-spacing:-.045em}.muted{color:var(--muted)}.flash{margin:16px 0;padding:12px 14px;border-radius:12px;background:#ecfdf5;color:#047857;border:1px solid #bbf7d0;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.grid-2{display:grid;grid-template-columns:1.3fr .7fr;gap:18px}.card{background:#fff;border:1px solid var(--line);border-radius:20px;padding:20px;box-shadow:0 8px 28px rgba(31,35,58,.045)}.card h2,.card h3{margin-top:0}.stat{min-height:125px}.stat .label{font-size:12px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.06em}.stat .value{font-size:34px;font-weight:900;margin-top:9px}.stat .sub{font-size:12px;color:var(--muted);margin-top:5px}
.profile-head{display:flex;align-items:center;gap:18px}.big-avatar{width:74px;height:74px;border-radius:22px;background:linear-gradient(135deg,#e8e6ff,#d7faf5);display:grid;place-items:center;font-size:27px;font-weight:900;color:#5149db}.profile-head h2{margin:0}.profile-head p{margin:5px 0 0;color:var(--muted)}
.tags{display:flex;flex-wrap:wrap;gap:8px}.tag{padding:7px 10px;border-radius:99px;background:#f1f2f7;color:#51596e;font-size:12px;font-weight:800}.tag.brand{background:#eeedff;color:#5149db}.list{display:grid;gap:10px}.list-item{padding:13px 14px;border:1px solid var(--line);border-radius:14px;display:flex;justify-content:space-between;gap:12px}.list-item strong{display:block}.list-item small{color:var(--muted)}
.form-card{max-width:760px;margin:auto}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.field label{display:block;font-size:12px;font-weight:900;color:#50586d;margin-bottom:7px}.field input,.field textarea,.field select{width:100%;border:1px solid #dddfea;background:#fbfbfd;border-radius:11px;padding:11px 12px;font:inherit;outline:none}.field textarea{min-height:110px;resize:vertical}.field input:focus,.field textarea:focus,.field select:focus{border-color:#aaa5ff;box-shadow:0 0 0 4px #eeedff}.full{grid-column:1/-1}.form-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:16px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}.toolbar input,.toolbar select{border:1px solid var(--line);background:#fff;border-radius:11px;padding:10px 12px;font:inherit}.toolbar input{min-width:250px}.opp{display:flex;flex-direction:column;gap:15px}.opp-top{display:flex;justify-content:space-between;gap:12px}.opp-title{font-size:19px;font-weight:900}.org{font-size:13px;color:var(--muted);margin-top:4px}.match{min-width:76px;text-align:right}.match b{color:var(--brand);font-size:20px}.match small{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;font-weight:800}.opp-meta{display:flex;gap:8px;flex-wrap:wrap}.meta{font-size:12px;background:#f6f7fb;border-radius:9px;padding:7px 9px;color:#5d6578}.opp-actions{display:flex;justify-content:space-between;align-items:center;gap:12px}.bar{height:7px;background:#eeeef5;border-radius:99px;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--brand),var(--teal));border-radius:inherit}.empty{text-align:center;padding:40px 20px;border:1px dashed #d6d8e4;border-radius:18px;background:#fbfbfd}.empty-icon{font-size:28px;margin-bottom:9px}.empty h3{margin:0 0 6px}.empty p{color:var(--muted);margin:0 0 17px}
.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse}.table th,.table td{text-align:left;padding:13px 10px;border-bottom:1px solid var(--line);font-size:13px}.table th{color:var(--muted);font-size:11px;text-transform:uppercase}.badge{display:inline-flex;padding:6px 8px;border-radius:99px;background:#eefcf4;color:#087443;font-size:11px;font-weight:900}.admin-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.login-wrap{min-height:calc(100vh - 72px);display:grid;place-items:center;padding:50px 0}.login-card{width:min(460px,100%);background:#fff;border:1px solid var(--line);border-radius:24px;padding:32px;box-shadow:var(--shadow)}.login-card h1{margin:0 0 8px}.login-card p{color:var(--muted)}.footer{padding:28px 0;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
@media(max-width:900px){.hero-grid,.grid-2{grid-template-columns:1fr}.cards,.grid{grid-template-columns:1fr 1fr}.steps{grid-template-columns:1fr 1fr}.admin-grid{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.container{width:min(100% - 24px,1180px)}.nav-in{height:auto;min-height:64px;flex-wrap:wrap;padding:10px 0}.navlinks{order:3;width:100%;overflow:auto;margin-left:0;padding-bottom:5px}.hero{padding:55px 0}.hero h1{font-size:46px}.cards,.grid,.steps,.form-grid,.admin-grid{grid-template-columns:1fr}.page-title{align-items:flex-start;flex-direction:column}.cta{flex-direction:column;align-items:flex-start}.toolbar input{width:100%;min-width:0}.opp-top{flex-direction:column}.match{text-align:left}.match b{font-size:17px}}
"""

BASE = r"""
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title or "SYNORA" }} · SkillSync</title>
<meta name="description" content="Build your profile. Showcase your skills. Discover your opportunities.">
<style>{{ css|safe }}</style></head><body>
<header class="nav"><div class="container nav-in">
<a class="brand" href="{{ url_for('home') }}"><span class="logo"></span><span>SYNORA</span></a>
{% if u %}
<nav class="navlinks">
<a href="{{ url_for('dashboard') }}">Dashboard</a><a href="{{ url_for('profile') }}">Portfolio</a>
<a href="{{ url_for('documents') }}">My Documents</a>
<a href="{{ url_for('opportunities') }}">Opportunities</a><a href="{{ url_for('applications') }}">Applications</a>
{% if u.role == 'admin' %}<a href="{{ url_for('admin') }}">Admin</a>{% endif %}
<a href="{{ url_for('logout') }}">Logout</a>
</nav>
<a class="user-pill" href="{{ url_for('profile') }}"><span class="avatar">{{ u.name[:1]|upper }}</span>{{ u.name }}</a>
{% else %}
<nav class="navlinks"><a href="{{ url_for('home') }}">Home</a><a href="{{ url_for('login') }}">Login</a><a class="btn btn-primary btn-sm" href="{{ url_for('register') }}">Get Started</a></nav>
{% endif %}
</div></header>
{% for m in get_flashed_messages() %}<div class="container"><div class="flash">✓ {{ m }}</div></div>{% endfor %}
{{ body|safe }}
<footer class="footer"><div class="container">© 2026 SYNORA · SkillSync · Build your profile. Showcase your skills. Discover your opportunities.</div></footer>
</body></html>
"""


def page(body_tpl, title="SYNORA", **ctx):
    return render_template_string(
        BASE, title=title, css=CSS, u=me(),
        body=render_template_string(body_tpl, **ctx)
    )


HOME = r"""
<section class="hero"><div class="container hero-grid">
<div>
<span class="eyebrow">Student career platform</span>
<h1>Build your profile.<br><span class="gradient">Showcase your skills.</span><br>Discover your opportunities.</h1>
<p>SYNORA brings your skills, projects, certifications and achievements into one professional portfolio — then helps you discover opportunities that fit what you already know.</p>
<div class="hero-actions"><a class="btn btn-primary" href="{{ url_for('register') }}">Build My Portfolio →</a><a class="btn btn-dark" href="{{ url_for('login') }}">Explore Opportunities</a></div>
</div>
<div class="hero-card"><div class="mock-top"><div><div class="mock-label">PROFILE STRENGTH</div><b>Career-ready profile</b></div><div class="score">82%</div></div>
<div class="progress"><i style="width:82%"></i></div><div class="mini-grid">
<div class="mini"><b>12 skills</b><span>Python · React · AWS</span></div><div class="mini"><b>8 projects</b><span>Web · Cloud · AI</span></div>
<div class="mini"><b>94% match</b><span>Frontend Internship</span></div><div class="mini"><b>6 badges</b><span>Achievements earned</span></div></div></div>
</div></section>
<section class="section"><div class="container"><div class="section-head"><div><h2>Everything for your next opportunity</h2><p>A focused workspace for student growth and discovery.</p></div></div>
<div class="cards">
<div class="feature"><div class="feature-icon">✦</div><h3>Professional Portfolio</h3><p>Turn coursework, projects, certifications and achievements into a polished digital profile.</p></div>
<div class="feature"><div class="feature-icon">◎</div><h3>Skill Matching</h3><p>Compare your skills with opportunity requirements using a simple, transparent percentage match.</p></div>
<div class="feature"><div class="feature-icon">↗</div><h3>Opportunity Discovery</h3><p>Find internships, hackathons, workshops and projects in one organized place.</p></div>
</div></div></section>
<section class="section" style="background:#fff"><div class="container"><div class="section-head"><div><h2>How SYNORA works</h2><p>Four simple steps from profile to opportunity.</p></div></div>
<div class="steps">
<div class="step"><span class="num">01 · PROFILE</span><h3>Build</h3><p>Add your education, skills, interests and career details.</p></div>
<div class="step"><span class="num">02 · SHOWCASE</span><h3>Prove it</h3><p>Present projects, certificates and achievements professionally.</p></div>
<div class="step"><span class="num">03 · MATCH</span><h3>Discover</h3><p>See how closely your skills align with available opportunities.</p></div>
<div class="step"><span class="num">04 · APPLY</span><h3>Take action</h3><p>Review the details and submit applications from your workspace.</p></div>
</div>
<div class="cta"><div><h2>Make your skills visible.</h2><p>Your next opportunity can start with a stronger profile.</p></div><a class="btn btn-primary" href="{{ url_for('register') }}">Start with SYNORA →</a></div>
</div></section>
"""


DASH = r"""
<div class="page"><div class="container">
<div class="page-title"><div><span class="eyebrow">Student workspace</span><h1 style="margin-top:10px">Welcome back, {{ u.name.split(' ')[0] }} 👋</h1><p class="muted">Keep your profile fresh and discover opportunities that match your strengths.</p></div><a class="btn btn-primary" href="{{ url_for('profile') }}">Edit Portfolio</a></div>
<div class="grid" style="margin-bottom:18px">
<div class="card stat"><div class="label">Profile completion</div><div class="value">{{ completion }}%</div><div class="progress" style="margin-top:10px"><i style="width:{{ completion }}%"></i></div></div>
<div class="card stat"><div class="label">Skills</div><div class="value">{{ u.skills|length }}</div><div class="sub">Skills in your profile</div></div>
<div class="card stat"><div class="label">Applications</div><div class="value">{{ application_count }}</div><div class="sub">Opportunities you applied to</div></div>
</div>
<div class="grid-2">
<div class="card"><h3>Profile overview</h3><div class="profile-head"><div class="big-avatar">{{ u.name[:1]|upper }}</div><div><h2>{{ u.name }}</h2><p>{{ u.education[0] if u.education else "Add your education to complete your profile." }}</p></div></div>
<hr style="border:0;border-top:1px solid var(--line);margin:20px 0"><h4>Skills overview</h4>
{% if u.skills %}<div class="tags">{% for s in u.skills %}<span class="tag brand">{{ s }}</span>{% endfor %}</div>{% else %}<div class="empty"><div class="empty-icon">✦</div><h3>No skills yet</h3><p>Add your strongest skills to improve opportunity matching.</p><a class="btn btn-soft btn-sm" href="{{ url_for('profile') }}">Add Skills</a></div>{% endif %}
</div>
<div class="card"><h3>Quick actions</h3><div class="list">
<a class="list-item" href="{{ url_for('profile') }}"><span><strong>✎ Update portfolio</strong><small>Keep your profile current</small></span>→</a>
<a class="list-item" href="{{ url_for('opportunities') }}"><span><strong>⌕ Find opportunities</strong><small>Explore your skill matches</small></span>→</a>
<a class="list-item" href="{{ url_for('applications') }}"><span><strong>✓ Track applications</strong><small>See your application status</small></span>→</a>
</div></div>
</div>
<div class="card" style="margin-top:18px"><div class="section-head"><div><h3>Recommended opportunities</h3><p>Sorted by your current skill match.</p></div><a class="btn btn-soft btn-sm" href="{{ url_for('opportunities') }}">View all</a></div>
<div class="grid">{% for o in recommended[:3] %}<div class="card opp" style="box-shadow:none"><div class="opp-top"><div><div class="opp-title">{{ o.title }}</div><div class="org">{{ o.org }}</div></div><div class="match"><b>{{ o.score }}%</b><small>match</small></div></div><div class="tags">{% for s in o.skills[:4] %}<span class="tag">{{ s }}</span>{% endfor %}</div><div class="bar"><i style="width:{{ o.score }}%"></i></div></div>{% else %}<div class="empty" style="grid-column:1/-1"><div class="empty-icon">⌁</div><h3>No opportunities yet</h3><p>New opportunities will appear here when they are posted.</p></div>{% endfor %}</div>
</div>
</div></div>
"""


PROFILE = r"""
<div class="page"><div class="container">
<div class="page-title"><div><span class="eyebrow">Digital portfolio</span><h1 style="margin-top:10px">My Portfolio</h1><p class="muted">Build a professional snapshot of what you can do.</p></div><div class="badge">{{ completion }}% complete</div></div>
<div class="grid-2">
<div>
{% for kind, label, icon in [('projects','Projects','⌁'),('certificates','Certifications','◇'),('achievements','Achievements','★'),('education','Education','▣')] %}
<div class="card" style="margin-bottom:16px"><div class="section-head"><div><h3>{{ icon }} {{ label }}</h3><p>{{ "Showcase your work and experience." if kind=="projects" else "Add relevant " + label.lower() + "." }}</p></div>
<form method="post" action="{{ url_for('portfolio_add', kind=kind) }}" style="display:flex;gap:7px"><input name="value" required placeholder="Add {{ label[:-1] if label.endswith('s') else label }}..." style="border:1px solid var(--line);border-radius:9px;padding:8px 10px"><button class="btn btn-primary btn-sm">Add</button></form></div>
{% if u[kind] %}<div class="list">{% for item in u[kind] %}<div class="list-item"><span>{{ item }}</span><form method="post" action="{{ url_for('portfolio_delete', kind=kind, index=loop.index0) }}" onsubmit="return confirm('Remove this item?')"><button class="btn btn-danger btn-sm">Remove</button></form></div>{% endfor %}</div>{% else %}<div class="empty"><div class="empty-icon">{{ icon }}</div><h3>No {{ label|lower }} yet</h3><p>Make your portfolio stronger by adding your first item.</p></div>{% endif %}</div>
{% endfor %}
</div>
<div>
<div class="card" style="margin-bottom:16px"><h3>Profile details</h3><form method="post" action="{{ url_for('profile') }}">
<div class="field"><label>Full name</label><input name="name" value="{{ u.name }}" required></div>
<div class="field"><label>Skills <span class="muted">(comma separated)</span></label><input name="skills" value="{{ ', '.join(u.skills) }}" placeholder="Python, React, AWS"></div>
<div class="field"><label>Interests <span class="muted">(comma separated)</span></label><input name="interests" value="{{ ', '.join(u.interests) }}" placeholder="Cloud Computing, Web Development"></div>
<div class="form-actions"><button class="btn btn-primary">Save profile</button></div></form></div>
<div class="card"><h3>Interests</h3>{% if u.interests %}<div class="tags">{% for i in u.interests %}<span class="tag">{{ i }}</span>{% endfor %}</div>{% else %}<div class="empty"><div class="empty-icon">◎</div><h3>No interests yet</h3><p>Add areas you want to explore.</p></div>{% endif %}</div>
</div></div></div>
"""
DOCUMENTS = r"""
<div class="page">
  <div class="container">
    <div class="page-title">
      <div>
        <span class="eyebrow">Personal library</span>
        <h1 style="margin-top:10px">My Documents</h1>
        <p class="muted">
          Upload and manage your resumes, certificates and academic documents.
        </p>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>Upload a document</h3>
        <p class="muted">PDF, DOCX, JPG or PNG · Maximum 10 MB</p>

        <form method="post"
              action="{{ url_for('documents') }}"
              enctype="multipart/form-data">
          <div class="field">
            <label>Document name</label>
            <input name="label" maxlength="100"
                   placeholder="e.g. Resume 2026">
          </div>

          <div class="field" style="margin-top:14px">
            <label>Document type</label>
            <select name="category" required>
              <option value="Resume">Resume</option>
              <option value="Certificate">Certificate</option>
              <option value="Academic Record">Academic Record</option>
              <option value="Project">Project Document</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div class="field" style="margin-top:14px">
            <label>Choose file</label>
            <input type="file" name="document"
                   accept=".pdf,.docx,.jpg,.jpeg,.png" required>
          </div>

          <div class="form-actions">
            <button class="btn btn-primary">Upload document</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h3>Your document library</h3>
        <div class="stat">
          <div class="label">Total documents</div>
          <div class="value">{{ documents|length }}</div>
        </div>
        <p class="muted">
          Your documents are stored privately and associated with your account.
        </p>
      </div>
    </div>

    <div class="card" style="margin-top:18px">
      <h3>Uploaded documents</h3>

      {% if documents %}
        <div class="list">
          {% for doc in documents %}
            <div class="list-item">
              <div style="min-width:0">
                <strong>{{ doc.label }}</strong>
                <small>
                  {{ doc.category }} · {{ doc.filename }}
                </small>
              </div>

              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <a class="btn btn-soft btn-sm"
                   href="{{ url_for('document_download', doc_id=doc.id) }}">
                  Download
                </a>
                <form method="post"
                      action="{{ url_for('document_delete', doc_id=doc.id) }}"
                      onsubmit="return confirm('Delete this document?')">
                  <button class="btn btn-danger btn-sm">Delete</button>
                </form>
              </div>
            </div>
          {% endfor %}
        </div>
      {% else %}
        <div class="empty">
          <div class="empty-icon">▤</div>
          <h3>No documents uploaded yet</h3>
          <p>Your uploaded resumes and certificates will appear here.</p>
        </div>
      {% endif %}
    </div>
  </div>
</div>
"""

OPPS = r"""
<div class="page"><div class="container">
<div class="page-title"><div><span class="eyebrow">Discover</span><h1 style="margin-top:10px">Opportunities</h1><p class="muted">Find roles that align with the skills in your portfolio.</p></div></div>
<form class="toolbar" method="get"><input name="q" value="{{ q }}" placeholder="Search opportunities, companies or skills…"><select name="type"><option value="">All categories</option>{% for t in types %}<option value="{{ t }}" {% if typ==t %}selected{% endif %}>{{ t }}</option>{% endfor %}<option value="Internship">Internship</option><option value="Hackathon">Hackathon</option><option value="Workshop">Workshop</option><option value="Project">Project</option></select><button class="btn btn-dark">Search</button></form>
<div class="grid">{% for o in ranked %}<div class="card opp"><div class="opp-top"><div><div class="opp-title">{{ o.title }}</div><div class="org">{{ o.org }}</div></div><div class="match"><b>{{ o.score }}%</b><small>skill match</small></div></div>
<div class="opp-meta"><span class="meta">◈ {{ o.type }}</span><span class="meta">⌖ {{ o.location or "Flexible" }}</span><span class="meta">◷ {{ o.deadline or "Open" }}</span></div>
<div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:800;color:var(--muted);margin-bottom:7px"><span>Required skills</span><span>{{ o.skills|length }} skills</span></div><div class="tags">{% for s in o.skills %}<span class="tag">{{ s }}</span>{% endfor %}</div></div>
<div class="bar"><i style="width:{{ o.score }}%"></i></div>
<div class="opp-actions">{% if o.id in applied %}<span class="badge">✓ Application submitted</span>{% else %}<span class="muted" style="font-size:12px">{{ o.score }}% of required skills matched</span><form method="post" action="{{ url_for('apply', oid=o.id) }}" onsubmit="return confirm('Apply to {{ o.title }}?')"><button class="btn btn-primary btn-sm">View Details & Apply</button></form>{% endif %}</div>
</div>{% else %}<div class="empty" style="grid-column:1/-1"><div class="empty-icon">⌕</div><h3>No matching opportunities</h3><p>Try clearing your search or check back when new opportunities are posted.</p><a class="btn btn-soft" href="{{ url_for('opportunities') }}">Clear filters</a></div>{% endfor %}</div>
</div></div>
"""


ADMIN = r"""
<div class="page"><div class="container">
<div class="page-title"><div><span class="eyebrow">Administration</span><h1 style="margin-top:10px">Control Center</h1><p class="muted">Manage students, opportunities and platform skills.</p></div></div>
<div class="admin-grid"><div class="card stat"><div class="label">Total Students</div><div class="value">{{ stats.students }}</div></div><div class="card stat"><div class="label">Total Opportunities</div><div class="value">{{ stats.opportunities }}</div></div><div class="card stat"><div class="label">Total Skills</div><div class="value">{{ stats.skills }}</div></div><div class="card stat"><div class="label">Active Opportunities</div><div class="value">{{ stats.active }}</div></div></div>
<div class="grid-2"><div class="card"><h3>Post an opportunity</h3><form method=post>
<div class="form-grid"><div class="field"><label>Title</label><input name=title required placeholder="Frontend Developer Internship"></div><div class="field"><label>Organization</label><input name=org required placeholder="Company / Team"></div>
<div class="field"><label>Category</label><select name=type><option>Internship</option><option>Hackathon</option><option>Workshop</option><option>Project</option></select></div><div class="field"><label>Mode / Location</label><input name=location placeholder="Remote | Chennai"></div>
<div class="field"><label>Deadline</label><input name=deadline placeholder="30 Nov 2026"></div><div class="field"><label>Duration</label><input name=duration placeholder="3 Months"></div>
<div class="field full"><label>Required skills</label><input name=skills required placeholder="React, JavaScript, HTML, CSS"></div></div>
<div class="form-actions"><button class="btn btn-primary">Publish opportunity</button></div></form></div>
<div class="card"><h3>Recent students</h3>{% if students %}<div class="list">{% for s in students[:7] %}<div class="list-item"><span><strong>{{ s.name }}</strong><small>{{ s.id }}</small></span><span class="badge">{{ s.skills|length }} skills</span></div>{% endfor %}</div>{% else %}<div class="empty"><h3>No students yet</h3><p>Registered students will appear here.</p></div>{% endif %}</div></div>
<div class="card" style="margin-top:18px"><h3>Opportunity management</h3><div class="table-wrap"><table class="table"><thead><tr><th>Opportunity</th><th>Organization</th><th>Category</th><th>Skills</th><th>Deadline</th></tr></thead><tbody>{% for o in ops %}<tr><td><b>{{ o.title }}</b></td><td>{{ o.org }}</td><td><span class="badge">{{ o.type }}</span></td><td>{{ ', '.join(o.skills) }}</td><td>{{ o.deadline or "Open" }}</td></tr>{% else %}<tr><td colspan=5>No opportunities posted yet.</td></tr>{% endfor %}</tbody></table></div></div>
</div></div>
"""


APPLICATIONS = r"""
<div class="page"><div class="container">
<div class="page-title"><div><span class="eyebrow">Application tracker</span><h1 style="margin-top:10px">Applications</h1><p class="muted">Keep track of where you are in your opportunity journey.</p></div></div>
<div class="card"><div class="table-wrap"><table class="table"><thead><tr><th>Opportunity</th>{% if u.role=='admin' %}<th>Student</th>{% endif %}<th>Status</th>{% if u.role=='admin' %}<th>Update</th>{% endif %}</tr></thead><tbody>
{% for a in apps %}<tr><td><b>{{ titles.get(a.opp, "Opportunity") }}</b></td>{% if u.role=='admin' %}<td>{{ a.student }}</td>{% endif %}<td><span class="badge">{{ a.status }}</span></td>{% if u.role=='admin' %}<td><form method=post style="display:flex;gap:7px"><input type=hidden name=id value="{{ a.id }}"><select name=status><option>Submitted</option><option>Shortlisted</option><option>Accepted</option><option>Rejected</option></select><button class="btn btn-soft btn-sm">Update</button></form></td>{% endif %}</tr>
{% else %}<tr><td colspan=4><div class="empty"><div class="empty-icon">✓</div><h3>No applications yet</h3><p>When you apply to an opportunity, it will appear here.</p><a class="btn btn-primary" href="{{ url_for('opportunities') }}">Explore opportunities</a></div></td></tr>{% endfor %}
</tbody></table></div></div></div></div>
"""


LOGIN = r"""
<div class="login-wrap"><div class="login-card"><span class="eyebrow">Welcome back</span><h1 style="margin-top:15px">Sign in to SYNORA</h1><p>Continue building your portfolio and discovering opportunities.</p>
<form method=post><div class="field"><label>Email</label><input name=email type=email required placeholder="you@example.com"></div><div class="field"><label>Password</label><input name=password type=password required placeholder="••••••••"></div><div class="form-actions"><button class="btn btn-primary" style="width:100%">Sign in →</button></div></form>
<p style="text-align:center;font-size:13px">New here? <a style="color:var(--brand);font-weight:800" href="{{ url_for('register') }}">Create an account</a></p></div></div>
"""

REGISTER = r"""
<div class="login-wrap"><div class="login-card"><span class="eyebrow">Start your profile</span><h1 style="margin-top:15px">Create your SYNORA account</h1><p>Build once. Showcase everywhere. Discover what fits you.</p>
<form method=post><div class="field"><label>Full name</label><input name=name required placeholder="Your name"></div><div class="field"><label>Email</label><input name=email type=email required placeholder="you@example.com"></div><div class="field"><label>Password</label><input name=password type=password minlength=6 required placeholder="At least 6 characters"></div><div class="form-actions"><button class="btn btn-primary" style="width:100%">Create account →</button></div></form>
<p style="text-align:center;font-size:13px">Already registered? <a style="color:var(--brand);font-weight:800" href="{{ url_for('login') }}">Sign in</a></p></div></div>
"""


@app.route("/")
def home():
    return page(HOME, title="SYNORA · Student Skill Platform")


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Please provide a name, valid email and password of at least 6 characters.")
            return redirect(url_for("register"))
        if db.get("students", email):
            flash("Email already registered. Please sign in.")
            return redirect(url_for("login"))
        db.put("students", {
            "id": email, "name": name, "pw": generate_password_hash(password),
            "role": "admin" if email == ADMIN_EMAIL else "student",
            "skills": [], "projects": [], "certificates": [], "interests": [],
            "achievements": [], "education": []
        })
        session["user"] = email
        flash("Welcome to SYNORA. Your portfolio is ready to build.")
        return redirect(url_for("dashboard"))
    return page(REGISTER, title="Create Account")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db.get("students", request.form.get("email", "").strip().lower())
        if u and check_password_hash(u["pw"], request.form.get("password", "")):
            session["user"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid credentials. Please check your email and password.")
    return page(LOGIN, title="Sign In")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    u = me()
    if not u:
        return redirect(url_for("login"))
    ensure_profile_fields(u)
    apps = [a for a in db.all("applications") if a["student"] == u["id"]]
    ranked = sorted(
        ({**o, "score": match_score(u["skills"], o.get("skills", []))} for o in db.all("opportunities")),
        key=lambda o: -o["score"]
    )
    return page(
        DASH, title="Dashboard", u=u, completion=profile_completion(u),
        application_count=len(apps), recommended=ranked
    )


@app.route("/profile", methods=["GET", "POST"])
def profile():
    u = me()
    if not u:
        return redirect(url_for("login"))
    ensure_profile_fields(u)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            u["name"] = name
        u["skills"] = split(request.form.get("skills"))
        u["interests"] = split(request.form.get("interests"))
        db.put("students", u)
        flash("Profile saved successfully.")
        return redirect(url_for("profile"))
    return page(PROFILE, title="My Portfolio", u=u, completion=profile_completion(u))


@app.route("/portfolio/<kind>/add", methods=["POST"])
def portfolio_add(kind):
    allowed = {"projects", "certificates", "achievements", "education"}
    u = me()
    if not u:
        return redirect(url_for("login"))
    if kind not in allowed:
        return redirect(url_for("profile"))
    value = request.form.get("value", "").strip()
    if not value:
        flash("Please enter a value before adding it.")
    else:
        ensure_profile_fields(u)
        u[kind].append(value)
        db.put("students", u)
        flash(f"{kind.capitalize()[:-1] if kind.endswith('s') else kind.capitalize()} added.")
    return redirect(url_for("profile"))


@app.route("/portfolio/<kind>/delete/<int:index>", methods=["POST"])
def portfolio_delete(kind, index):
    allowed = {"projects", "certificates", "achievements", "education"}
    u = me()
    if not u:
        return redirect(url_for("login"))
    ensure_profile_fields(u)
    if kind in allowed and 0 <= index < len(u[kind]):
        u[kind].pop(index)
        db.put("students", u)
        flash("Portfolio item removed.")
    return redirect(url_for("profile"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    u = me()
    if not u or u["role"] != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        org = request.form.get("org", "").strip()
        skills = split(request.form.get("skills"))
        if not title or not org or not skills:
            flash("Title, organization and required skills are required.")
            return redirect(url_for("admin"))
        db.put("opportunities", {
            "id": uuid.uuid4().hex[:8], "title": title, "type": request.form.get("type", "Internship"),
            "org": org, "skills": skills, "location": request.form.get("location", "").strip(),
            "deadline": request.form.get("deadline", "").strip(), "duration": request.form.get("duration", "").strip()
        })
        flash("Opportunity published successfully.")
        return redirect(url_for("admin"))
    students = [ensure_profile_fields(s) for s in db.all("students")]
    ops = db.all("opportunities")
    skill_set = {x.lower() for s in students for x in s.get("skills", [])}
    stats = {
        "students": len(students),
        "opportunities": len(ops),
        "skills": len(skill_set),
        "active": sum(1 for o in ops if not o.get("deadline") or o.get("deadline") >= str(date.today()))
    }
    return page(ADMIN, title="Admin Control Center", students=students, ops=ops, stats=stats)


@app.route("/opportunities")
def opportunities():
    u = me()
    if not u:
        return redirect(url_for("login"))
    ensure_profile_fields(u)
    q = request.args.get("q", "").strip().lower()
    typ = request.args.get("type", "").strip()
    all_ops = db.all("opportunities")
    ranked = []
    for o in all_ops:
        haystack = " ".join([o.get("title", ""), o.get("org", ""), o.get("type", ""), *o.get("skills", [])]).lower()
        if q and q not in haystack:
            continue
        if typ and o.get("type") != typ:
            continue
        ranked.append({**o, "score": match_score(u["skills"], o.get("skills", []))})
    ranked.sort(key=lambda o: (-o["score"], o.get("title", "").lower()))
    applied = {a["opp"] for a in db.all("applications") if a["student"] == u["id"]}
    types = sorted({o.get("type", "") for o in all_ops if o.get("type")})
    return page(OPPS, title="Opportunities", ranked=ranked, applied=applied, q=q, typ=typ, types=types)


@app.route("/apply/<oid>", methods=["POST"])
def apply(oid):
    u = me()
    if not u:
        return redirect(url_for("login"))
    if db.get("opportunities", oid):
        key = f"{u['id']}#{oid}"
        if not db.get("applications", key):
            db.put("applications", {"id": key, "student": u["id"], "opp": oid, "status": "Submitted"})
            flash("Application submitted successfully.")
        else:
            flash("You have already applied to this opportunity.")
    return redirect(url_for("applications"))


@app.route("/applications", methods=["GET", "POST"])
def applications():
    u = me()
    if not u:
        return redirect(url_for("login"))
    if request.method == "POST" and u["role"] == "admin":
        a = db.get("applications", request.form.get("id", ""))
        if a:
            a["status"] = request.form.get("status", "Submitted")
            db.put("applications", a)
            flash("Application status updated.")
    apps = db.all("applications") if u["role"] == "admin" else [a for a in db.all("applications") if a["student"] == u["id"]]
    titles = {o["id"]: o["title"] for o in db.all("opportunities")}
    return page(APPLICATIONS, title="Applications", apps=apps, titles=titles, u=u)


@app.route("/api/match")
def api_match():
    skills, req = split(request.args.get("skills")), split(request.args.get("required"))
    return jsonify(score=match_score(skills, req))

import boto3



def get_s3():
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET is not configured.")
    return boto3.client(
        "s3",
        region_name="ap-south-1",
        endpoint_url="https://s3.ap-south-1.amazonaws.com"
    )


def get_user_documents(u):
    return u.setdefault("documents", [])


@app.route("/documents", methods=["GET", "POST"])
def documents():
    u = me()
    if not u:
        return redirect(url_for("login"))

    docs = get_user_documents(u)

    if request.method == "POST":
        file = request.files.get("document")
        label = request.form.get("label", "").strip()
        category = request.form.get("category", "Other")

        if not file or not file.filename:
            flash("Please choose a file.")
            return redirect(url_for("documents"))

        filename = secure_filename(file.filename)
        if not filename or "." not in filename:
            flash("Invalid filename.")
            return redirect(url_for("documents"))

        extension = filename.rsplit(".", 1)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            flash("File type not allowed.")
            return redirect(url_for("documents"))

        if category not in {
            "Resume", "Certificate", "Academic Record", "Project", "Other"
        }:
            flash("Invalid document category.")
            return redirect(url_for("documents"))

        # The browser's content type is not trusted; inspect the file signature
        # or use a dedicated validation library before production deployment.
        doc_id = uuid.uuid4().hex
        key = f"student-documents/{uuid.uuid4().hex}/{filename}"

        try:
            s3 = get_s3()
            s3.upload_fileobj(
                file,
                S3_BUCKET,
                key,
                ExtraArgs={
                    "ContentType": file.mimetype or "application/octet-stream",
                    "Metadata": {"owner": uuid.uuid5(
                        uuid.NAMESPACE_URL, u["id"]
                    ).hex}
                }
            )
        except (ClientError, RuntimeError) as exc:
            app.logger.exception("Document upload failed")
            flash("Upload failed. Check the S3 configuration and permissions.")
            return redirect(url_for("documents"))

        docs.append({
            "id": doc_id,
            "label": label or filename,
            "filename": filename,
            "category": category,
            "s3_key": key
        })
        db.put("students", u)
        flash("Document uploaded successfully.")
        return redirect(url_for("documents"))

    return page(
        DOCUMENTS,
        title="My Documents",
        u=u,
        documents=docs
    )


@app.route("/documents/<doc_id>/download")
def document_download(doc_id):
    u = me()
    if not u:
        return redirect(url_for("login"))

    doc = next(
        (d for d in get_user_documents(u) if d["id"] == doc_id),
        None
    )
    if not doc:
        abort(404)

    try:
        
        url = get_s3().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": doc["s3_key"]
            },
            ExpiresIn=300
        )
        return redirect(url)

    except (ClientError, RuntimeError):
        app.logger.exception("Document download link failed")
        abort(503)

    return redirect(url)


@app.route("/documents/<doc_id>/delete", methods=["POST"])
def document_delete(doc_id):
    u = me()
    if not u:
        return redirect(url_for("login"))

    docs = get_user_documents(u)
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        abort(404)

    try:
        get_s3().delete_object(
            Bucket=S3_BUCKET,
            Key=doc["s3_key"]
        )
    except (ClientError, RuntimeError):
        app.logger.exception("Document deletion failed")
        flash("Could not delete the document from storage.")
        return redirect(url_for("documents"))

    u["documents"] = [d for d in docs if d["id"] != doc_id]
    db.put("students", u)
    flash("Document deleted successfully.")
    return redirect(url_for("documents"))

application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
