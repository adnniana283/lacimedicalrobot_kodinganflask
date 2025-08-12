# lacimedicalrobot_kodinganflask
jalankan wifi
jalankan xampp

# Instalasi Library yang Diperlukan :
Flask
Flask-Cors
opencv-python
numpy
requests
mysql-connector-python
python-dotenv
python 3.12.4 --version

Konfigurasi :
# Kunci rahasia untuk sesi Flask (bisa diisi string acak yang panjang)
SECRET_KEY="ganti_dengan_kunci_rahasia_anda"

# Kredensial Database MySQL
DB_HOST="localhost"
DB_USER="root"
DB_PASSWORD="password_database_anda"
DB_NAME="nama_database_anda"

# URL dan Access Key untuk Antares
ANTARES_URL="https://platform.antares.id:8443/..."
ANTARES_ACCESS_KEY="kunci_akses_antares_anda"

# Alamat IP dari ESP32-CAM Anda
ESP32_IP_ADDRESS="http://192.168.1.10"

>> Koneksi Jaringan 
Koneksi Internet: Komputer yang menjalankan server Flask ini harus memiliki koneksi internet yang aktif untuk dapat berkomunikasi dengan server Antares.
Jaringan Lokal (Wi-Fi): Agar server Flask dapat menerima streaming video dari ESP32, keduanya harus terhubung ke jaringan Wi-Fi yang sama.
>> Server Pihak Ketiga: Antares
Aplikasi ini terintegrasi dengan platform IoT Antares untuk mengirim atau menerima data.
Pastikan Anda memiliki akun Antares yang aktif.
URL Antares dan Access Key yang Anda masukkan di file .env harus benar dan valid.
>> Perangkat Keras: ESP32
Pastikan program pada ESP32 Anda sudah berjalan dan modul tersebut sudah terhubung ke Wi-Fi.
Alamat IP ESP32 yang Anda masukkan di file .env harus merupakan alamat IP yang benar dan dapat diakses dari komputer yang menjalankan server Flask ini.
Anda biasanya dapat melihat alamat IP ini di Serial Monitor Arduino IDE saat ESP32 pertama kali terhubung ke Wi-Fi.

# run kode flask
klik (open) pada alamat yang tercantum pada console
untuk stop gunakan "Ctrl + C"

# vidio
https://drive.google.com/drive/folders/13higa1tsNdIWJ0wBxUVL6zjnaa5zw3jC?usp=sharing 
