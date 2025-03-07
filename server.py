from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "Sekhar@26"  # for session management ?



# MySQL 
def create_db_connection():
    return mysql.connector.connect(
        host="maglev.proxy.rlwy.net",
        user="root",
        password="LtDesPnVOBexjBjwmlMcsmsTfXCbsoiU",
        database="help_db",
        port=30133
    )

# Function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template("index.html")


@app.route('/register', methods=['GET', 'POST'])
def register():
    error_message = None
    
    if request.method == 'POST':
        name = request.form['name']
        aadhar_number = request.form['aadhar_number']
        mobile_number = request.form['mobile_number']
        password = request.form['password']  
        #session['password'] = password

        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists in data_users
        cursor.execute("SELECT * FROM data_users WHERE aadhar = %s AND mobile = %s", (aadhar_number, mobile_number))
        data = cursor.fetchone()  # Fetch only one record

        if not data: 
            error_message = "User does not exist in database!"
        else:
            try:
                # Inserting users into table
                cursor.execute("INSERT INTO users (name, aadhar_number, mobile_number, password, help_provided) VALUES (%s, %s, %s, %s, 0)", 
                               (name, aadhar_number, mobile_number, password))
                
                conn.commit()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for('login'))
            except mysql.connector.IntegrityError:
                error_message = "User already exists! Try logging in."
        
        conn.close() 

    return render_template("register.html", error_message=error_message)

from flask import Flask, request, redirect, url_for, session, render_template
from werkzeug.security import check_password_hash

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        aadhar_number = request.form['aadhar_number']
        mobile_number = request.form['mobile_number']
        passwordd = request.form['password']

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, password FROM users WHERE aadhar_number=%s AND mobile_number=%s", 
                       (aadhar_number, mobile_number))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and passwordd==user['password']:  
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid Credentials"

    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("dashboard.html", user_name=session['user_name'])

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT name, aadhar_number, mobile_number, help_provided FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    #cursor.execute("SELECT COUNT(*) AS request_count FROM requests WHERE user_id = %s", (user_id,))
    #request_count = cursor.fetchone()["request_count"]

    cursor.execute("SELECT help_requested FROM users WHERE id = %s", (user_id,))
    request_count = cursor.fetchone()["help_requested"]

    conn.close()

    if not user:
        return "User not found", 404

    return render_template("profile.html", user=user, request_count=request_count, help_provided=user['help_provided'])


# Upload folder configuration
UPLOAD_FOLDER = "HELP/static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)  # Ensure folder exists

@app.route('/request_help', methods=['GET', 'POST'])
def request_help():
    if request.method == 'POST':
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user_id = session['user_id']
        category = request.form.get('category')
        amount = request.form.get('amount')
        description = request.form.get('description')
        location = request.form.get('location')
        code= request.form.get('code')
        #Uploading a file 
        file = request.files.get("file")
        image_url = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            print("FILE NAME: ",filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file_path=file_path.replace("\\","/")
            print("FILE PATH: ",file_path)
            file.save(file_path)
            image_url = f"static/uploads/{filename}"  # relative path
            print("IMAGE URL: ",image_url)

        conn = create_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO requests (user_id, category, amount, description, image_url, location, code) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, category, amount if amount else None, description, image_url, location,code)
        )
        cursor.execute("UPDATE users SET help_requested = help_requested + 1 WHERE id = %s", (user_id,))

        conn.commit()
        conn.close()

        return redirect(url_for('browse_requests'))

    return render_template("request_help.html")

@app.route('/browse_requests')
def browse_requests():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # only logged-in users can browse

    user_id = session['user_id'] 

    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all requests 
    cursor.execute("SELECT id, user_id, category, amount, description, image_url FROM requests")
    requests = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template("browse_requests.html", requests=requests, user_id=user_id)

@app.route('/offer_help/<int:request_id>')
def offer_help(request_id):
    if 'user_id' not in session:
        flash("You must be logged in to offer help.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']  
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch request details along with the requester's ID and secret code in one query
    cursor.execute("""
        SELECT requests.id, requests.user_id, users.name, users.mobile_number, 
               requests.category, requests.amount, requests.description, 
               requests.image_url, requests.location, requests.code  -- Fetch the secret code too
        FROM requests
        JOIN users ON requests.user_id = users.id
        WHERE requests.id = %s
    """, (request_id,))
    
    request_details = cursor.fetchone()

    cursor.execute("SELECT help_provided, help_requested FROM users WHERE id=%s", (request_details['user_id'],))
    user_details = cursor.fetchone()


    # Checking-- if request exists before proceeding
    if not request_details:
        flash("Request not found.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('browse_requests'))

    # Preventing: users from helping their own requests
    if request_details['user_id'] == user_id:
        flash("You cannot offer help on your own request!", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('browse_requests'))

    return render_template('offer_help.html', request_details=request_details,user_details=user_details)


@app.route('/verify_code/<int:request_id>', methods=['POST'])
def verify_code(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    entered_code = request.form.get("entered_code")

    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT code FROM requests WHERE id = %s", (request_id,))
    request_data = cursor.fetchone()
    conn.close()

    if request_data and request_data["code"] == entered_code:
        session['verified_request_id'] = request_id  # Store verified request onnnly in session
        flash("Code verified! You can now offer help.", "success")
    else:
        flash("Invalid code! Please try again.", "error")

    return redirect(url_for('offer_help', request_id=request_id))


@app.route('/confirm_help/<int:request_id>', methods=['POST'])
def confirm_help(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = create_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET help_provided = help_provided + 1 WHERE id = %s", (user_id,))
   
    cursor.execute("DELETE FROM requests WHERE id = %s", (request_id,))
    
    conn.commit()
    conn.close()

    return redirect(url_for('browse_requests'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = create_db_connection()
    cursor = conn.cursor()

    # Ensure the user can only delete their own requests
    cursor.execute("DELETE FROM requests WHERE id = %s", (request_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('browse_requests'))

if __name__ == "__main__":
    app.run(debug=True)
    
