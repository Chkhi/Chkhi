from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        database=os.environ.get('DB_NAME', 'my_clinic'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', ''),
        sslmode=os.environ.get('PGSSLMODE', 'require')
    )

@app.route('/')
def home():
    return jsonify({'message': 'API работает! Используйте /api/patient/1 для получения данных'})

@app.route('/api/patient/<int:patient_id>')
def get_patient(patient_id):
    # ... ваш существующий код ...
    pass

# ========== НОВЫЙ МАРШРУТ ДЛЯ РЕГИСТРАЦИИ ==========
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        
        required_fields = ['firstName', 'lastName', 'email', 'password', 'birthDate']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Поле {field} обязательно'}), 400
        
        first_name = data['firstName']
        last_name = data['lastName']
        patronymic = data.get('patronymic', '')
        email = data['email']
        password = data['password']
        birth_date = data['birthDate']
        phone = data.get('phone', '')
        address = data.get('address', '')
        gender = data.get('gender', '')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT patient_id FROM patients WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Пользователь с таким email уже существует'}), 409
        
        cur.execute("""
            INSERT INTO patients (first_name, last_name, patronymic, birth_date, gender, phone, email, address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING patient_id
        """, (first_name, last_name, patronymic, birth_date, gender, phone, email, address))
        
        patient_id = cur.fetchone()[0]
        
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cur.execute("""
            INSERT INTO users (patient_id, email, password_hash, role)
            VALUES (%s, %s, %s, 'patient')
        """, (patient_id, email, password_hash))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Регистрация успешна!',
            'patientId': patient_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
