#ini yang (dipake) karena udah konek ke mysql
from flask import Flask, render_template, Response, jsonify, request, session, redirect, url_for, flash
import cv2
import numpy as np
import time
from datetime import datetime
import requests
import threading
from flask_cors import CORS
from threading import Lock
import mysql.connector
from dotenv import load_dotenv
import os

 
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
CORS(app)
lock = Lock()
network_log = []
failed_requests = 0
enroll_done_flag = False
stop_enroll_stream = False
PIN_BENAR = "1234"

# Drawer state global
drawer_states = {
    "A": "closed",
    "B": "closed",
    "C": "closed"
}

access_status = {"access": "Waiting for access...", "time": ""}

# URL ESP32 dan Antares
esp32_url = "http://192.168.128.236/control"
antares_url = "https://platform.antares.id:8443/~/antares-cse/antares-id/Robot_smartdrawer/Lid_control"
antares_headers = {
    "Content-Type": "application/json;ty=4",
    "Accept": "application/json",
    "X-M2M-Origin": "86c5118ee18245a7:632fa4dfbbc3eeee"
}

# Fungsi insert MySQL
def insert_to_mysql(user, laci, status, confidence):
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='smartdrawer_db'
        )
        cursor = conn.cursor()
        sql = """
        INSERT INTO access_log (user_name, drawer, access_status, confidence, timestamp)
        VALUES (%s, %s, %s, %s, NOW())
        """
        access_text = "Granted" if status == 1 else "Denied"
        cursor.execute(sql, (user, laci, access_text, confidence))
        conn.commit()
        cursor.close()
        conn.close()
        print("[MySQL] Data inserted")
    except mysql.connector.Error as err:
        print("[MySQL Error]", err)

# Kirim ke ESP32
def send_esp32_command(drawer_id, action, source="unknown"):
    global network_log, failed_requests
    try:
        payload = {"laci": drawer_id, "aksi": action}
        start_time = time.time()
        response = requests.post(esp32_url, json=payload)
        duration = time.time() - start_time

        with lock:
            network_log.append((time.time(), len(response.content), duration))
        print(f"[ESP32] Status {response.status_code}: {response.text}")
        with lock:
            drawer_states[drawer_id] = action
        return True
    except Exception as e:
        failed_requests += 1
        print(f"[ESP32 CMD ERROR] Failed to send to drawer {drawer_id}: {e}")
        return False


# Kirim ke Antares + ESP32 + MySQL
def send_antares_status(user, laci, status, confidence=0):
    access_text = "Access Granted" if status == 1 else "Access Denied"
    payload = {
        "m2m:cin": {
            "con": f'{{"status":{status}, "Access":"{access_text}", "User":"{user}", "Laci":"{laci}"}}'
        }
    }
    try:
        r = requests.post(antares_url, json=payload, headers=antares_headers)
        print(f"[Antares] {r.status_code}: {access_text} - {user} - {laci}")
    except Exception as e:
        print("[Antares Error]", e)

    try:
        if laci != "None":
            aksi = "open" if status == 1 else "close"
            esp32_payload = {"laci": laci[-1], "aksi": aksi}
            r2 = requests.post(esp32_url, json=esp32_payload)
            print(f"[ESP32] {r2.status_code}: {r2.text}")
            with lock:
                drawer_states[laci[-1]] = aksi
    except Exception as e:
        print("[ESP32 Error]", e)

    insert_to_mysql(user, laci, status, confidence)

    access_status["access"] = f"{access_text} - {user} - {laci}"
    access_status["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Model dan kamera
cap = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier(r'Smart_Laci\face_recognition_pc\haarcascade_frontalface_default.xml')
model = cv2.face.LBPHFaceRecognizer_create()
model.read(r"Smart_Laci\face_recognition_pc\models\1model_lbph_final.yml")

labels = np.array(['S1', 'S10', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9'])

laci_access = {
    'S1': 'Laci A', 'S10': 'Laci A', 'S2': 'Laci A', 'S3': 'Laci B', 'S4': 'Laci A',
    'S5': 'Laci B', 'S6': 'Laci B', 'S7': 'Laci C', 'S8': 'Laci C', 'S9': 'Laci C'
}

def draw_face_box(img, label, x0, y0, xt, yt):
    (w, h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
    cv2.rectangle(img, (x0, y0 + baseline), (xt, yt), (0, 255, 255), 3)
    cv2.rectangle(img, (x0, y0 - h), (x0 + w, y0 + baseline), (0, 255, 255), -1)
    cv2.putText(img, label, (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (50, 50, 50), 2, cv2.LINE_AA)

@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login_pin'))
    return render_template("index.html")

@app.route('/login_pin', methods=['GET', 'POST'])
def login_pin():
    if request.method == 'POST':
        input_pin = request.form.get('pin')
        conn = None  # Inisialisasi di luar try
        try:
            # 1. Hubungkan ke database
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='smartdrawer_db'
            )
            # 2. Buat cursor setelah koneksi berhasil
            cursor = conn.cursor()
            
            # 3. Jalankan query
            cursor.execute("SELECT pin FROM pin_table WHERE pin = %s", (input_pin,))
            result = cursor.fetchone()

            # 4. Proses hasil
            if result:
                session['authenticated'] = True
                return redirect(url_for('index'))
            else:
                flash('PIN salah. Coba lagi.', 'danger')
                return redirect(url_for('login_pin'))

        except mysql.connector.Error as err:
            # Tangani jika ada error database
            print(f"[DB ERROR in login_pin]: {err}")
            flash(f"Database Error: {err}", 'danger')
            return redirect(url_for('login_pin'))
        
        finally:
            # 5. Pastikan koneksi selalu ditutup
            if conn and conn.is_connected():
                conn.close()
                print("[DB INFO] Connection closed from login_pin.")

    # Jika metodenya GET, cukup tampilkan halaman login
    return render_template('login_pin.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login_pin'))

@app.route('/setup_pin', methods=['GET', 'POST'])
def setup_pin():
    if request.method == 'POST':
        new_pin = request.form.get('new_pin')
        conn = None
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='smartdrawer_db')
            cursor = conn.cursor()
            

            cursor.execute("INSERT INTO pin_table (pin) VALUES (%s)", (new_pin,))
            conn.commit()
            
            flash('PIN berhasil diatur/diubah!', 'success')
            return redirect(url_for('login_pin'))
        except mysql.connector.Error as err:
            flash(f'Database Error: {err}', 'danger')
            return redirect(url_for('setup_pin'))
        finally:
            if conn and conn.is_connected():
                conn.close()

    # Tampilkan halaman setup_pin.html tanpa memeriksa database terlebih dahulu
    return render_template('setup_pin.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/control_drawer', methods=['POST'])
def control_drawer_json():
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'message': 'Content-Type must be application/json'}), 400

        data = request.get_json()
        drawer_input = data.get("drawer")
        action = data.get("action")

        if not drawer_input or not action:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

        if isinstance(drawer_input, int) or (isinstance(drawer_input, str) and drawer_input.isdigit()):
            drawer_num = int(drawer_input)
            if drawer_num not in [1, 2, 3]:
                return jsonify({'status': 'error', 'message': 'Invalid drawer number'}), 400
            drawer_letter = chr(64 + drawer_num)
        else:
            drawer_letter = str(drawer_input).upper()
            if drawer_letter not in ['A', 'B', 'C']:
                return jsonify({'status': 'error', 'message': 'Invalid drawer letter'}), 400

        if action.lower() not in ['open', 'close']:
            return jsonify({'status': 'error', 'message': 'Invalid action'}), 400

        success = send_esp32_command(drawer_letter, action.lower(), source="web_button")

        if success:
            insert_to_mysql(
                user="Staf",
                laci=f"Laci {drawer_letter}",
                status=1 if action.lower() == 'open' else 0,
                confidence=0
            )
            return jsonify({
                'status': 'success',
                'message': f'Drawer {drawer_letter} {action.lower()} command sent successfully',
                'drawer_state': drawer_states.get(drawer_letter, 'unknown')
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to send command to ESP32'}), 500

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    return jsonify({
        'status': 'success',
        'message': 'Test endpoint working',
        'method': request.method,
        'data': request.get_json() if request.method == 'POST' else None,
        'drawer_states': drawer_states,
        'esp32_url': esp32_url
    })

@app.route('/esp32_status')
def esp32_status():
    """Check ESP32 connection status"""
    try:
        # Test ping ke ESP32 - ubah endpoint test
        test_url = "http://192.168.128.236/status"  # atau endpoint lain yang ada di ESP32
        r = requests.get(test_url, timeout=5)
        if r.status_code == 200:
            return jsonify({
                'status': 'connected', 
                'esp32_ip': esp32_url,
                'response': r.text[:100]  # ambil 100 karakter pertama
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': f'ESP32 returned status {r.status_code}',
                'esp32_ip': esp32_url
            })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'disconnected', 
            'error': 'Connection refused - ESP32 might be offline',
            'esp32_ip': esp32_url
        })
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'disconnected', 
            'error': 'Connection timeout',
            'esp32_ip': esp32_url
        })
    except Exception as e:
        return jsonify({
            'status': 'disconnected', 
            'error': str(e),
            'esp32_ip': esp32_url
        })

@app.route('/test_esp32')
def test_esp32():
    """Test ESP32 connection dengan berbagai cara"""
    results = {}
    
    # Test 1: Ping basic
    try:
        r = requests.get("http://192.168.128.236/", timeout=3)
        results['basic_ping'] = f"Status: {r.status_code}, Response: {r.text[:50]}"
    except Exception as e:
        results['basic_ping'] = f"Error: {str(e)}"
    
    # Test 2: Test control endpoint
    try:
        r = requests.get("http://192.168.128.236/control", timeout=3)
        results['control_endpoint'] = f"Status: {r.status_code}"
    except Exception as e:
        results['control_endpoint'] = f"Error: {str(e)}"
    
    # Test 3: Test status endpoint
    try:
        r = requests.get("http://192.168.128.236/status", timeout=3)
        results['status_endpoint'] = f"Status: {r.status_code}, Response: {r.text}"
    except Exception as e:
        results['status_endpoint'] = f"Error: {str(e)}"
    
    return jsonify(results)

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found',
        'error': '404 Not Found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Internal server error',
        'error': '500 Internal Server Error'
    }), 500


@app.route('/status')
def status():
    return jsonify(access_status)

@app.route('/drawer_states')
def get_drawer_states():
    with lock:
        return jsonify(drawer_states)

@app.route('/enroll')
def enroll_page():
    return render_template("enroll.html")

@app.route('/enroll_video')
def enroll_video():
    return Response(enroll_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/enroll_form')
def enroll_form():
    return render_template('enroll_form.html')  # ini nanti isi form HTML-nya

@app.route('/enroll_camera')
def enroll_camera():
    # Ambil data dari URL parameter
    patient_id = request.args.get("patient_id", "")
    name_prefix = request.args.get("name_prefix", "")
    num_photos = request.args.get("num_photos", 10)

    return render_template('enroll_camera.html',
                           patient_id=patient_id,
                           name_prefix=name_prefix,
                           num_photos=num_photos)

@app.route('/video_enroll')
def video_enroll():
    patient_id = request.args.get("patient_id", "unknown")
    name_prefix = request.args.get("name_prefix", "User")
    num_photos = int(request.args.get("num_photos", 10))
    return Response(enroll_frames(patient_id, name_prefix, num_photos),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/enroll_status')
def enroll_status():
    return jsonify({'done': enroll_done_flag})

@app.route('/enroll_done')
def enroll_done():
    return """
    <html>
    <head>
      <title>Enroll Selesai</title>
      <style>
        body { text-align: center; padding-top: 50px; font-family: sans-serif; background-color: #f2f2f2; }
        .btn {
          padding: 12px 24px;
          background-color: #2d7d7b;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 1rem;
          cursor: pointer;
          text-decoration: none;
        }
      </style>
    </head>
    <body>
      <h2>✅ Pengambilan Foto Selesai</h2>
      <p>Silakan kembali ke halaman utama</p>
      <a href="/" class="btn">⬅️ Kembali ke Halaman Utama</a>
    </body>
    </html>
    """
@app.route('/stop_enroll')
def stop_enroll():
    global stop_enroll_stream
    stop_enroll_stream = True
    return "Enroll stream stopped"

def enroll_frames(patient_id, name_prefix, num_photos=10):
    global stop_enroll_stream
    global enroll_done_flag

    stop_enroll_stream = False
    enroll_done_flag = False

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[ERROR] Kamera gagal dibuka.")
        return

    count = 0
    delay = 0.5

    try:
        while count < num_photos and not stop_enroll_stream:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Gagal mengambil frame dari kamera.")
                break

            label = f"Ambil Foto {count+1}/{num_photos}"
            cv2.putText(frame, label, (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            is_success, buffer = cv2.imencode(".jpg", frame)
            if is_success:
                insert_to_mysql_enroll(patient_id, f"{name_prefix}_{count+1:03d}", buffer.tobytes())

            count += 1
            time.sleep(delay)

            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    except GeneratorExit:
        print("[INFO] Browser client menutup stream enroll.")
    except Exception as e:
        print(f"[ERROR] enroll_frames exception: {e}")
    finally:
        if cap.isOpened():
            cap.release()
            print("[INFO] Kamera dilepaskan dari enroll_frames.")
        enroll_done_flag = True
        stop_enroll_stream = True



def insert_to_mysql_enroll(patient_id, name, image_bytes, note="Enroll via web"):
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartdrawer_db"
        )
        cursor = conn.cursor()
        sql = """
        INSERT INTO face_dataset (patient_id, name, image_blob, created_at, note)
        VALUES (%s, %s, %s, NOW(), %s)
        """
        cursor.execute(sql, (patient_id, name, image_bytes, note))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[ENROLL] Foto {name} disimpan ke DB")
    except mysql.connector.Error as err:
        print("[MySQL Error - Enroll]", err)


def insert_to_db(patient_id, name, image_bytes, note=""):
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartdrawer_db"
        )
        cursor = conn.cursor()
        query = """
            INSERT INTO face_dataset (patient_id, name, image_blob, created_at, note)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (patient_id, name, image_bytes, datetime.now(), note))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[MySQL] Foto {name} disimpan.")
    except mysql.connector.Error as err:
        print("[MySQL Error]", err)

def capture_frames(patient_id, name_prefix, num_photos=10):
    cap = cv2.VideoCapture(0)
    count = 0

    def save_image(frame, count):
        is_success, buffer = cv2.imencode(".jpg", frame)
        if is_success:
            insert_to_db(patient_id, f"{name_prefix}_{count:04d}", buffer.tobytes(), "Enroll via Web")

    while count < num_photos:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("Capture Photo", frame)
        threading.Thread(target=save_image, args=(frame.copy(), count)).start()
        count += 1

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

@app.route('/enroll_patient', methods=['POST'])
def enroll_patient():
    data = request.get_json()
    patient_id = data.get('patient_id')
    name_prefix = data.get('prefix')

    if not patient_id or not name_prefix:
        return jsonify({'status': 'error', 'message': 'Data tidak lengkap'}), 400

    threading.Thread(target=capture_frames, args=(patient_id, name_prefix)).start()

    return jsonify({'status': 'success', 'message': f'Proses perekaman {name_prefix} dimulai.'})

    
def get_face_direction(x, y, w, h, frame_width, frame_height):
    cx = x + w // 2
    cy = y + h // 2

    dx = cx - frame_width // 2
    dy = cy - frame_height // 2

    direction = "Wajah Terdeteksi"

    if abs(dx) > 100:
        if dx > 0:
            direction = "Geser ke kanan sedikit"
        else:
            direction = "Geser ke kiri sedikit"
    elif abs(dy) > 80:
        if dy > 0:
            direction = "Mundur sedikit"
        else:
            direction = "Maju ke depan"

    return direction



def gen_frames():
    # Menggunakan cv2.CAP_DSHOW untuk performa lebih baik di Windows
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) 
    last_sent = time.time()
    last_detected = time.time()
    prev_status = 0
    last_laci = None
    last_user = None

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)

        status = 0
        name = "Unknown"
        laci = "None"
        face_detected = False
        frame_height, frame_width = frame.shape[:2]
        label_status = "Tidak Ada Wajah"
        label_color = (0, 0, 255) # Merah

        if len(faces) > 0:
            for (x, y, w, h) in faces:
                face_img = gray[y:y+h, x:x+w]
                face_img = cv2.resize(face_img, (100, 100))
                idx, conf = model.predict(face_img)

                # --- PERUBAHAN DIMULAI DI SINI ---
                # Memeriksa apakah 'idx' yang didapat dari model valid untuk list 'labels'
                if idx < len(labels):
                    # Semua logika di bawah ini hanya berjalan jika idx valid,
                    # sehingga mencegah IndexError.
                    
                    name = labels[idx]
                    conf = round(conf, 2)

                    # Anda bisa menyesuaikan nilai confidence ini
                    if conf > 95: 
                        name = "Unknown"
                        label_status = "Wajah Tidak Dikenal"
                    else:
                        face_detected = True
                        direction_label = get_face_direction(x, y, w, h, frame_width, frame_height)
                        label_status = direction_label
                        label_color = (0, 255, 0) # Hijau

                    laci = laci_access.get(name, "None")
                    status = 1 if name != "Unknown" and laci != "None" else 0

                    label = f"{name} ({conf}%)"
                    draw_face_box(frame, label, x, y, x+w, y+h)

                    if face_detected and status == 1 and "Terdeteksi" in label_status and time.time() - last_sent > 5:
                        send_antares_status(name, laci, 1, confidence=conf)
                        last_sent = time.time()
                        last_detected = time.time()
                        last_user = name
                        last_laci = laci
                        prev_status = 1
                # --- AKHIR DARI PERUBAHAN ---

        # 🔐 Auto-close jika tidak ada wajah terdeteksi selama > 5 detik
        if not face_detected and prev_status == 1 and time.time() - last_detected > 5:
            if last_laci is not None and last_user is not None:
                print("[Auto Close] Tidak ada wajah, menutup laci:", last_laci)
                send_antares_status(last_user, last_laci, 0, confidence=0)
                prev_status = 0
                last_laci = None
                last_user = None

        cv2.putText(frame, label_status, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, label_color, 3)
        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# Jangan lupa melepaskan kamera jika loop berhenti
cap.release()

@app.route('/network_metrics_report')
def network_metrics_report():
    import matplotlib.pyplot as plt
    from fpdf import FPDF
    import os
    from datetime import datetime

    # Pastikan ada data yang cukup untuk diproses (minimal 2 log)
    if len(network_log) < 2:
        return "Data log belum cukup untuk membuat laporan.", 200

    # Ekstrak data dari log
    timestamps = [log[0] for log in network_log]
    sizes = [log[1] for log in network_log]
    delays = [log[2] for log in network_log]

    # Ubah UNIX timestamp menjadi objek datetime untuk plotting
    datetimes = [datetime.fromtimestamp(ts) for ts in timestamps]

    # --- Persiapan Direktori ---
    save_dir = os.path.join(os.path.dirname(__file__), 'laci_pintar_project', 'static')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # ===================================================================
    # 1. GRAFIK DATA DELAY (Line Plot, Menggantikan Histogram)
    # ===================================================================
    plt.figure(figsize=(10, 5))
    frames = range(1, len(delays) + 1)
    plt.plot(frames, delays, color='steelblue')
    plt.title("Data Delay")
    plt.xlabel("Jumlah Aktivitas (Frame)")
    plt.ylabel("Delay (s)")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(f"{save_dir}/delay.png")
    plt.close()

    # ===================================================================
    # 2. GRAFIK DATA JITTER
    # ===================================================================
    jitter_ms = [abs(delays[i] - delays[i - 1]) * 1000 for i in range(1, len(delays))]
    jitter_frames = range(1, len(jitter_ms) + 1)
    plt.figure(figsize=(10, 5))
    plt.plot(jitter_frames, jitter_ms, color='steelblue')
    plt.title("Data Jitter")
    plt.xlabel("Jumlah Aktivitas (Frame)")
    plt.ylabel("Jitter (ms)")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(f"{save_dir}/jitter.png")
    plt.close()

    # ===================================================================
    # 3. GRAFIK DATA FPS (Diadaptasi menjadi Aktivitas per Detik)
    # ===================================================================
    time_diffs = [(timestamps[i] - timestamps[i-1]) for i in range(1, len(timestamps))]
    # Hindari pembagian dengan nol jika waktu sama persis
    fps_values = [1.0 / diff if diff > 0 else 0 for diff in time_diffs]
    fps_times = datetimes[1:] # Plot FPS mulai dari data kedua
    plt.figure(figsize=(10, 5))
    plt.plot(fps_times, fps_values, color='steelblue')
    plt.title("Data FPS (Aktivitas per Detik)")
    plt.xlabel("Waktu Aktivitas")
    plt.ylabel("Aktivitas per Detik (FPS)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(f"{save_dir}/fps.png")
    plt.close()

    # ===================================================================
    # 4. GRAFIK DATA THROUGHPUT
    # ===================================================================
    # Throughput (kbps) = (ukuran data dalam byte * 8) / (selisih waktu * 1000)
    throughput_kbps = [(sizes[i] * 8) / (diff * 1000) if diff > 0 else 0 for i, diff in enumerate(time_diffs, 1)]
    throughput_times = datetimes[1:] # Plot throughput mulai dari data kedua
    plt.figure(figsize=(10, 5))
    plt.plot(throughput_times, throughput_kbps, color='steelblue')
    plt.title("Data Throughput")
    plt.xlabel("Waktu Aktivitas")
    plt.ylabel("Throughput (kbps)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(f"{save_dir}/throughput.png")
    plt.close()

    # ===================================================================
    # PEMBUATAN FILE PDF (Diperbarui)
    # ===================================================================
    # Kalkulasi packet loss
    # Anda perlu memastikan variabel failed_requests ada dan terdefinisi di scope ini
    # Jika tidak ada, definisikan, contoh: failed_requests = 0 
    total_requests = len(network_log) + failed_requests
    loss = (failed_requests / total_requests) * 100 if total_requests > 0 else 0
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "Laporan Metrik Jaringan - Laci Pintar", ln=True, align='C')
    pdf.cell(200, 10, f"Total Request Berhasil: {len(network_log)}", ln=True)
    pdf.cell(200, 10, f"Gagal Request: {failed_requests}", ln=True)
    pdf.cell(200, 10, f"Packet Loss: {loss:.2f}%", ln=True)
    
    # Masukkan semua gambar baru ke PDF
    # Pastikan nama file cocok dengan yang disimpan (delay.png bukan delay_histogram.png)
    for img in ['delay.png', 'jitter.png', 'fps.png', 'throughput.png']:
        image_path = os.path.join(save_dir, img)
        if os.path.exists(image_path):
            pdf.image(image_path, w=180)
            pdf.ln(5) # Memberi jarak antar gambar

    pdf.output(f"{save_dir}/network_report.pdf")

    return render_template("network_report.html")

def jalankan_misi_terjadwal(mission_plan):
    """
    FUNGSI PLACEHOLDER UNTUK EKSEKUTOR MISI.
    Di sinilah sistem navigasi Anda akan menerima seluruh rencana misi.
    """
    print(f"--- RENCANA MISI DITERIMA ---")
    print(f"Total tugas dalam jadwal: {len(mission_plan)}")
    
    # --- CONTOH INTEGRASI ---
    # Di dunia nyata, fungsi ini akan memanggil sistem navigasi Anda
    # dengan tugas pertama, menunggu selesai, lalu lanjut ke tugas kedua, dst.
    # Ini adalah simulasi sederhana dari eksekusi misi berurutan.
    for i, task in enumerate(mission_plan):
        print(f"--> Menjalankan Tugas #{i+1}:")
        print(f"    Tujuan: {task['destination']}, Subjek: {task['subject_id']}")
        # Panggil fungsi navigasi Anda di sini untuk satu tugas
        # panggil_sistem_navigasi(task['destination'], task['subject_id'])
        time.sleep(2) # Simulasi waktu eksekusi
    
    print(f"--- SEMUA TUGAS SELESAI ---")
    return True, "Seluruh misi dalam jadwal telah selesai dieksekusi."


@app.route('/jadwal_page')
def jadwal_page():
    """Halaman utama sekarang akan mengarahkan ke halaman login."""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Menangani proses login."""
    error = None
    if request.method == 'POST':
        pin_input = request.form['pin']
        if pin_input == PIN_BENAR:
            # Jika PIN benar, simpan status login di session
            session['logged_in'] = True
            # Arahkan ke halaman jadwal
            return redirect(url_for('halaman_jadwal'))
        else:
            # Jika PIN salah, kirim pesan error ke template
            error = 'PIN yang Anda masukkan salah.'
    
    # Jika metodenya GET atau login gagal, tampilkan halaman login
    return render_template('login_pin.html', error=error)

@app.route('/jadwal')
def halaman_jadwal():
    """Menampilkan halaman penjadwalan, tapi diproteksi."""
    # Cek apakah pengguna sudah login
    if not session.get('logged_in'):
        # Jika belum, tendang kembali ke halaman login
        return redirect(url_for('login'))
    
    # Jika sudah login, tampilkan halaman jadwal
    return render_template('jadwal.html')

@app.route('/start_mission', methods=['POST'])
def start_mission():
    """Menerima jadwal misi (juga perlu diproteksi)."""
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Akses ditolak. Silakan login."}), 401

    mission_plan = request.get_json()
    # ... (sisa logika start_mission Anda tetap sama) ...
    print(f"Misi diterima: {mission_plan}")
    return jsonify({"success": True, "message": "Misi berhasil dimulai."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
