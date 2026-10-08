import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Item, Claim

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-this-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///unifind.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB file upload limit

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables upon startup
with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def index():
    category = request.args.get('category')
    status = request.args.get('status')
    search_query = request.args.get('q')

    query = Item.query

    if category and category != 'All':
        query = query.filter_by(category=category)
    if status and status != 'All':
        query = query.filter_by(status=status)
    if search_query:
        query = query.filter(Item.title.contains(search_query) | Item.description.contains(search_query))

    items = query.order_by(Item.date_posted.desc()).all()
    return render_template('index.html', items=items)

@app.route('/report', methods=['GET', 'POST'])
@login_required
def report_item():
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        status = request.form.get('status')
        location = request.form.get('location')
        description = request.form.get('description')
        verification_question = request.form.get('verification_question')

        file = request.files.get('image')
        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_item = Item(
            title=title,
            category=category,
            status=status,
            location=location,
            description=description,
            verification_question=verification_question,
            image_filename=filename,
            user_id=current_user.id
        )
        db.session.add(new_item)
        db.session.commit()
        flash('Item successfully reported!', 'success')
        return redirect(url_for('index'))

    return render_template('report.html')

@app.route('/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'POST':
        verification_answer = request.form.get('verification_answer')
        
        existing_claim = Claim.query.filter_by(item_id=item.id, user_id=current_user.id).first()
        if existing_claim:
            flash('You have already submitted a claim for this item.', 'warning')
        else:
            new_claim = Claim(
                item_id=item.id,
                user_id=current_user.id,
                verification_answer=verification_answer
            )
            db.session.add(new_claim)
            db.session.commit()
            flash('Claim submitted! Security/Finder will verify your response.', 'info')
            
        return redirect(url_for('item_detail', item_id=item.id))

    return render_template('item_detail.html', item=item)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        reg_number = request.form.get('reg_number')
        password = request.form.get('password')

        if User.query.filter((User.email == email) | (User.reg_number == reg_number)).first():
            flash('Email or Registration Number already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password, method='scrypt')
        user = User(full_name=full_name, email=email, reg_number=reg_number, password_hash=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid login details.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)