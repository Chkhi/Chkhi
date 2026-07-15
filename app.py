from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime
import hashlib

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

# ===================== ГЛАВНАЯ СТРАНИЦА =====================
@app.route('/')
def home():
    return jsonify({'message': 'API работает! Используйте /api/patient/1 для получения данных'})

# ===================== ПОЛУЧЕНИЕ ДАННЫХ ПАЦИЕНТА =====================
@app.route('/api/patient/<int:patient_id>')
def get_patient(patient_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Данные пациента
        cur.execute("""
            SELECT patient_id, first_name, last_name, patronymic, 
                   birth_date, phone, email
            FROM patients 
            WHERE patient_id = %s
        """, (patient_id,))
        patient = cur.fetchone()
        
        if not patient:
            return jsonify({'error': 'Пациент не найден'}), 404
        
        # Зубная карта
        cur.execute("""
            SELECT tooth_number, status, notes
            FROM teeth_status
            WHERE patient_id = %s
            ORDER BY tooth_number
        """, (patient_id,))
        teeth = cur.fetchall()
        
        # История посещений
        cur.execute("""
            SELECT v.visit_date, v.diagnosis, v.treatment, v.cost,
                   d.first_name, d.last_name, d.specialization
            FROM visits v
            JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE v.patient_id = %s
            ORDER BY v.visit_date DESC
        """, (patient_id,))
        visits = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'patient': {
                'id': patient[0],
                'firstName': patient[1],
                'lastName': patient[2],
                'patronymic': patient[3] or '',
                'birthDate': patient[4].strftime('%d.%m.%Y') if patient[4] else None,
                'phone': patient[5] or '',
                'email': patient[6]
            },
            'teeth': [
                {'number': t[0], 'status': t[1], 'notes': t[2] or ''}
                for t in teeth
            ],
            'visits': [
                {
                    'date': v[0].strftime('%d.%m.%Y %H:%M') if v[0] else None,
                    'diagnosis': v[1] or '',
                    'treatment': v[2] or '',
                    'cost': float(v[3]) if v[3] else 0,
                    'doctor': f"{v[4]} {v[5]}" if v[4] else '',
                    'specialization': v[6] or ''
                }
                for v in visits
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===================== РЕГИСТРАЦИЯ =====================
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
        
        # Проверяем, существует ли пользователь
        cur.execute("SELECT patient_id FROM patients WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Пользователь с таким email уже существует'}), 409
        
        # Вставляем пациента
        cur.execute("""
            INSERT INTO patients (first_name, last_name, patronymic, birth_date, gender, phone, email, address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING patient_id
        """, (first_name, last_name, patronymic, birth_date, gender, phone, email, address))
        
        patient_id = cur.fetchone()[0]
        
        # Хешируем пароль
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Создаём пользователя
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

# ===================== ВХОД =====================
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email и пароль обязательны'}), 400
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT u.user_id, u.patient_id, u.role, p.first_name, p.last_name
            FROM users u
            JOIN patients p ON u.patient_id = p.patient_id
            WHERE u.email = %s AND u.password_hash = %s
        """, (email, password_hash))
        
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            return jsonify({
                'success': True,
                'userId': user[0],
                'patientId': user[1],
                'role': user[2],
                'fullName': f"{user[3]} {user[4]}"
            })
        else:
            return jsonify({'error': 'Неверный email или пароль'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===================== ПОЛУЧЕНИЕ ДАННЫХ АВТОРИЗОВАННОГО ПОЛЬЗОВАТЕЛЯ =====================
@app.route('/api/me/<int:patient_id>')
def get_current_user(patient_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Данные пациента
        cur.execute("""
            SELECT patient_id, first_name, last_name, patronymic, 
                   birth_date, phone, email
            FROM patients 
            WHERE patient_id = %s
        """, (patient_id,))
        patient = cur.fetchone()
        
        if not patient:
            return jsonify({'error': 'Пациент не найден'}), 404
        
        # Зубная карта
        cur.execute("""
            SELECT tooth_number, status, notes
            FROM teeth_status
            WHERE patient_id = %s
            ORDER BY tooth_number
        """, (patient_id,))
        teeth = cur.fetchall()
        
        # История посещений
        cur.execute("""
            SELECT v.visit_date, v.diagnosis, v.treatment, v.cost,
                   d.first_name, d.last_name, d.specialization
            FROM visits v
            JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE v.patient_id = %s
            ORDER BY v.visit_date DESC
        """, (patient_id,))
        visits = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'patient': {
                'id': patient[0],
                'firstName': patient[1],
                'lastName': patient[2],
                'patronymic': patient[3] or '',
                'birthDate': patient[4].strftime('%d.%m.%Y') if patient[4] else None,
                'phone': patient[5] or '',
                'email': patient[6]
            },
            'teeth': [
                {'number': t[0], 'status': t[1], 'notes': t[2] or ''}
                for t in teeth
            ],
            'visits': [
                {
                    'date': v[0].strftime('%d.%m.%Y %H:%M') if v[0] else None,
                    'diagnosis': v[1] or '',
                    'treatment': v[2] or '',
                    'cost': float(v[3]) if v[3] else 0,
                    'doctor': f"{v[4]} {v[5]}" if v[4] else '',
                    'specialization': v[6] or ''
                }
                for v in visits
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
