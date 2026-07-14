from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Разрешаем запросы с любых сайтов

# --- ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ---
def get_db_connection():
    # Если вы размещаете на Render.com — данные будут из переменных окружения
    # Если запускаете локально — используйте эти настройки
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        database=os.environ.get('DB_NAME', 'dentistry_clinic'),
        user=os.environ.get('DB_USER', 'website_user'),
        password=os.environ.get('DB_PASSWORD', 'Новый_Пароль_2026!')  # ЗАМЕНИТЕ!
    )

# --- API: ПОЛУЧИТЬ ДАННЫЕ ПАЦИЕНТА ---
@app.route('/api/patient/<int:patient_id>')
def get_patient(patient_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Данные пациента
        cur.execute("""
            SELECT patient_id, first_name, last_name, patronymic, 
                   birth_date, phone, email, registration_date
            FROM patients 
            WHERE patient_id = %s
        """, (patient_id,))
        patient = cur.fetchone()
        
        if not patient:
            return jsonify({'error': 'Пациент не найден'}), 404
        
        # 2. Зубная карта
        cur.execute("""
            SELECT tooth_number, status, notes, updated_at
            FROM teeth_status
            WHERE patient_id = %s
            ORDER BY tooth_number
        """, (patient_id,))
        teeth = cur.fetchall()
        
        # 3. История посещений
        cur.execute("""
            SELECT v.visit_id, v.visit_date, v.diagnosis, v.treatment, 
                   v.cost, v.status,
                   d.first_name, d.last_name, d.specialization
            FROM visits v
            JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE v.patient_id = %s
            ORDER BY v.visit_date DESC
        """, (patient_id,))
        visits = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Форматируем данные в JSON
        return jsonify({
            'patient': {
                'id': patient[0],
                'firstName': patient[1],
                'lastName': patient[2],
                'patronymic': patient[3] or '',
                'birthDate': patient[4].strftime('%d.%m.%Y') if patient[4] else None,
                'phone': patient[5] or '',
                'email': patient[6],
                'registrationDate': patient[7].strftime('%d.%m.%Y') if patient[7] else None
            },
            'teeth': [
                {
                    'number': t[0],
                    'status': t[1],
                    'notes': t[2] or '',
                    'updatedAt': t[3].strftime('%d.%m.%Y %H:%M') if t[3] else None
                } for t in teeth
            ],
            'visits': [
                {
                    'id': v[0],
                    'date': v[1].strftime('%d.%m.%Y %H:%M') if v[1] else None,
                    'diagnosis': v[2] or '',
                    'treatment': v[3] or '',
                    'cost': float(v[4]) if v[4] else 0,
                    'status': v[5] or '',
                    'doctor': f"{v[6]} {v[7]}" if v[6] else '',
                    'specialization': v[8] or ''
                } for v in visits
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API: РЕГИСТРАЦИЯ (опционально) ---
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        first_name = data.get('firstName')
        last_name = data.get('lastName')
        email = data.get('email')
        password = data.get('password')
        birth_date = data.get('birthDate')
        phone = data.get('phone')
        
        # Здесь должна быть валидация и хеширование пароля
        # Для простоты пропустим
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Вставляем пациента
        cur.execute("""
            INSERT INTO patients (first_name, last_name, birth_date, phone, email)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING patient_id
        """, (first_name, last_name, birth_date, phone, email))
        
        patient_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'patientId': patient_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API: ВХОД (опционально) ---
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        # Для простоты пропускаем проверку пароля
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT u.user_id, u.patient_id, p.first_name, p.last_name
            FROM users u
            JOIN patients p ON u.patient_id = p.patient_id
            WHERE u.email = %s
        """, (email,))
        
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            return jsonify({
                'success': True,
                'userId': user[0],
                'patientId': user[1],
                'fullName': f"{user[2]} {user[3]}"
            })
        else:
            return jsonify({'error': 'Пользователь не найден'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- ЗАПУСК ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)