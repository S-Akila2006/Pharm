from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
from datetime import datetime, timedelta

from pymysql.cursors import Cursor
from models import db
from models import Medicine
app = Flask(__name__)
app.secret_key = 'b1A@9x$7!dK&2mC*PqR^FgT#XyZ'

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:mysql@localhost/pharmacy'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()



# Database Configuration
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "mysql"
DB_NAME = "pharmacy"

def connect_db():
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)

# Home/Login Page
@app.route('/', methods=['GET', 'POST'])
def home():
    session.pop('_flashes', None)
    logout = True
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        conn.close()


        if user:
            session['username'] = username
            logout = False
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('home.html', logout=logout)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, expiry_date, quantity FROM medicines")
    medicines = cursor.fetchall()
    conn.close()

    # Check for medicines expiring soon, expired, low stock, and critical stock
    today = datetime.today().date()
    soon_to_expire = []
    expired = []
    low_stock = []
    critical_stock = []

    for medicine in medicines:
        name, expiry_date, quantity = medicine
        # Expiry checks
        if expiry_date <= today:
            expired.append((name, expiry_date))
        elif expiry_date <= today + timedelta(days=90):
            soon_to_expire.append((name, expiry_date))
        # Stock checks
        if quantity <= 5:
            critical_stock.append((name, quantity))
        elif quantity <= 10:
            low_stock.append((name, quantity))

    # Flash message for critical stock
    if critical_stock:
        flash(f'Warning: {len(critical_stock)} medicine(s) are critically low in stock!', 'danger')
    elif low_stock:
        flash(f'Notice: {len(low_stock)} medicine(s) are running low in stock.', 'warning')

    return render_template('dashboard.html',
                         expired=expired,
                         soon_to_expire=soon_to_expire,
                         low_stock=low_stock,
                         critical_stock=critical_stock)

# Add Medicine Page
@app.route('/add_medicine', methods=['GET', 'POST'])
def add_medicine():
    if 'username' not in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form['name']
        brand = request.form['brand']
        price = float(request.form['price'])
        discount = float(request.form['discount'])
        quantity = int(request.form['quantity'])
        expiry_date = request.form['expiry_date']
        batch_no = request.form['batch_no']
        batch_date = request.form['batch_date']

        # Calculate final price
        final_price = round(price * (1 - discount / 100), 2)

        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM medicines")
            count = cursor.fetchone()[0]

            id = count + 1
            cursor.execute("""
                INSERT INTO medicines (id, name, brand, price, discount, final_price, quantity, expiry_date, batch_no, batch_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (id, name, brand, price, discount, final_price, quantity, expiry_date, batch_no, batch_date))
            flash('New medicine added successfully!', 'success')

            conn.commit()
            conn.close()
        except Exception as e:
            flash(f'Error: {e}', 'danger')

    return render_template('add_medicine.html')


# Get Medicine Details Page
@app.route('/get_medicine', methods=['GET', 'POST'])
def get_medicine():
    if 'username' not in session:
        return redirect(url_for('home'))

    result = None
    error = None

    if request.method == 'POST':
        name = request.form['name']
        brand = request.form['brand']

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, brand, price, discount, final_price, quantity, expiry_date, batch_no, batch_date 
            FROM medicines 
            WHERE name = %s AND brand = %s 
            ORDER BY id DESC LIMIT 1
        """, (name, brand))
        result = cursor.fetchone()
        conn.close()

        if not result:
            error = "Medicine not found!"
        else:
            # Ensure final_price is calculated if not stored in DB
            final_price = result[4] if result[4] is not None else round(result[2] * (1 - result[3] / 100), 2)

    return render_template('get_medicine.html', result={'name': result[0], 'brand': result[1], 'price': result[2], 'discount': int(result[3]), 'final_price': final_price,
                               'quantity': result[5], 'expiry_date': result[6], 'batch_no': result[7], 'batch_date': result[8] }
    if result else None, error=error)


# batch medicines page
@app.route('/batch_medicines', methods=['GET', 'POST'])
def batch_medicines():
    if request.method == 'POST':
        batch_no = request.form['batch_no']
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, brand, price, quantity, expiry_date FROM medicines WHERE batch_no = %s", (batch_no,))
        medicines = cursor.fetchall()
        conn.close()

        if medicines:
            return render_template('batch_medicines.html', medicines=medicines, batch_no=batch_no)
        else:
            flash('No medicines found for this batch number.', 'warning')
            return render_template('batch_medicines.html', medicines=[], batch_no=batch_no)

    return render_template('batch_medicines.html', medicines=None)

# search medicines
@app.route('/search_medicine')
def search_medicine():
    query = request.args.get('q', '')
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name FROM medicines WHERE name LIKE %s", (query + '%',))
    results = cursor.fetchall()
    return jsonify([row[0] for row in results])

@app.route('/get_brands')
def get_brands():
    medicine = request.args.get('medicine', '')
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT brand FROM medicines WHERE name = %s", (medicine,))
    results = cursor.fetchall()
    brands = [row[0] for row in results]  # Just strings
    return jsonify(brands)

@app.route('/search_brands')
def search_brands():
    medicine = request.args.get('medicine', '')
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT brand, quantity FROM medicines WHERE name = %s", (medicine,))
    results = cursor.fetchall()

    brands = [{"brand": row[0], "quantity": row[1]} for row in results]
    return jsonify(brands)


# search discounts
@app.route('/best_offer', methods=['GET'])
def best_offer():
    medicine_name = request.args.get('name')
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT brand, discount, price
        FROM medicines 
        WHERE name = %s 
        ORDER BY discount DESC 
        LIMIT 1
    """, (medicine_name,))

    result = cursor.fetchone()

    if result:
        brand, discount, price = result
        final_price = price - (price * discount / 100)
        return jsonify({
            'brand': brand,
            'discount': discount,
            'price': price,
            'final_price': round(final_price, 2)
        })
    else:
        return jsonify({'error': 'No brand found for this medicine'}), 404

@app.route('/low_stock_report')
def low_stock_report():
    if 'username' not in session:
        return redirect(url_for('home'))

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, brand, quantity, batch_no, expiry_date 
        FROM medicines 
        WHERE quantity <= 10 
        ORDER BY quantity ASC
    """)
    low_stock_medicines = cursor.fetchall()
    conn.close()

    return render_template('low_stock_report.html', low_stock_medicines=low_stock_medicines)

@app.route('/sell_medicine', methods=['GET', 'POST'])
def sell_medicine():
    if 'username' not in session:
        return redirect(url_for('home'))

    conn = connect_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        medicine = request.form['medicine']
        brand = request.form['brand']
        quantity = int(request.form['quantity'])

        # Get batches ordered by expiry date
        cursor.execute("""
            SELECT id, quantity, expiry_date, price, discount 
            FROM medicines 
            WHERE name = %s AND brand = %s AND quantity > 0 
            ORDER BY expiry_date ASC
        """, (medicine, brand))
        batches = cursor.fetchall()

        if not batches:  # Check if batches is empty
            flash(f'No stock available for {medicine} ({brand}).', 'warning')
            conn.close()
            return redirect('/sell_medicine')

        total_available = sum(batch[1] for batch in batches)

        if total_available < quantity:
            flash('Not enough stock available.', 'warning')
        else:
            remaining_qty = quantity
            total_price = 0
            price_per_strip = batches[0][3]  # Price from the first batch
            discount_per_strip = batches[0][4]  # Discount from the first batch

            for batch in batches:
                batch_id, batch_qty, expiry, price, discount = batch

                if remaining_qty == 0:
                    break

                if batch_qty >= remaining_qty:
                    total_price += remaining_qty * price * (1 - discount / 100)
                    cursor.execute("UPDATE medicines SET quantity = quantity - %s WHERE id = %s", (remaining_qty, batch_id))
                    remaining_qty = 0
                else:
                    total_price += batch_qty * price * (1 - discount / 100)
                    cursor.execute("UPDATE medicines SET quantity = 0 WHERE id = %s", (batch_id,))
                    remaining_qty -= batch_qty

            # Insert sale record into sales table with sale_date
            sale_date = datetime.now()
            cursor.execute("""
                INSERT INTO sales (medicine_name, brand, quantity, price, discount, sale_date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (medicine, brand, quantity, price_per_strip, discount_per_strip, sale_date))

            conn.commit()
            flash(f'Successfully sold {quantity} strips of {medicine} ({brand}).', 'success')

        conn.close()
        return redirect('/sell_medicine')

    # GET request
    cursor.execute("SELECT DISTINCT name FROM medicines")
    medicines = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template("sell_medicine.html", medicines=medicines)

@app.route('/sales_history')
def sales_history():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT medicine_name, brand, quantity, price, discount, sale_date 
        FROM sales
        ORDER BY sale_date DESC
    """)
    rows = cursor.fetchall()

    sales = []
    for row in rows:
        medicine_name = row[0]
        brand = row[1]
        quantity = row[2]
        price = row[3] or 0.0  # Price per strip
        discount = row[4] or 0.0
        sale_date = row[5]# Discount percentage per strip

        # Total price before discount = price per strip * quantity
        total_price_before_discount = round(price * quantity, 2)

        # Cumulative discount percentage for display and calculation = discount% * quantity
        cumulative_discount = round(discount * quantity, 2)

        # Total discount amount = total_price_before_discount * cumulative_discount%
        discount_amount = round(total_price_before_discount * cumulative_discount / 100, 2)

        # Total price after discount = total_price_before_discount - discount_amount
        total_price_after_discount = round(total_price_before_discount - discount_amount, 2)

        sales.append({
            'medicine_name': medicine_name,
            'brand': brand,
            'quantity': quantity,
            'price_based_on_quantity': total_price_before_discount,
            'discount': cumulative_discount,
            'total_price': total_price_after_discount,
            'sale_date': sale_date
        })

    conn.close()
    return render_template("sales_history.html", sales=sales)

@app.route('/delete_medicine', methods=['GET', 'POST'])
def delete_medicine():
    if 'username' not in session:
        return redirect(url_for('home'))

    conn = connect_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        medicine_name = request.form['medicine_name']
        batch_no = request.form['batch_no']

        # Check if the medicine with the given name and batch number exists
        cursor.execute("SELECT COUNT(*) FROM medicines WHERE name = %s AND batch_no = %s", (medicine_name, batch_no))
        count = cursor.fetchone()[0]

        if count == 0:
            flash(f'No medicine found with name "{medicine_name}" in batch number "{batch_no}".', 'warning')
        else:
            # Delete the medicine record(s)
            cursor.execute("DELETE FROM medicines WHERE name = %s AND batch_no = %s", (medicine_name, batch_no))
            conn.commit()
            flash(f'Successfully deleted all records of "{medicine_name}" with batch number "{batch_no}".', 'success')

        conn.close()
        return redirect(url_for('delete_medicine'))

    # GET request: Render the delete form
    conn.close()
    return render_template("delete_medicine.html")

@app.route('/medicine_suggestions', methods=['GET'])
def medicine_suggestions():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    query = request.args.get('query', '').strip()
    if not query:
        return jsonify([])

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name FROM medicines WHERE name LIKE %s LIMIT 10", (query + '%',))
    medicines = [row[0] for row in cursor.fetchall()]
    conn.close()

    return jsonify(medicines)

@app.route('/sales_dates', methods=['GET', 'POST'])
def sales_dates():
    sale_records = []
    name = ''
    brand = ''

    if request.method == 'POST':
        name = request.form['name']
        brand = request.form['brand']

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT medicine_name, brand, sale_date 
            FROM sales 
            WHERE medicine_name = %s AND brand = %s
            ORDER BY sale_date DESC
        """, (name, brand))
        sale_records = cursor.fetchall()
        conn.close()

    return render_template('sales_dates.html', sale_records=sale_records, name=name, brand=brand)





# Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    logout = True
    flash('You have been logged out successfully', 'info')
    return render_template('home.html', logout=logout)

# Debugging Route to Check Session
@app.route('/check_session')
def check_session():
    return session.get('username', 'No user logged in')


if __name__ == '__main__':
    app.run(debug=True)
