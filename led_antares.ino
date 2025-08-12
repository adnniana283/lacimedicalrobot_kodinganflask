#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>

const char* ssid = "infinixhot";
const char* password = "12345maribersama";

const char* ap_ssid = "SmartDrawer_AP";
const char* ap_password = "drawer123";

const char* antares_api_key = "86c5118ee18245a7:632fa4dfbbc3eeee";
const char* antares_url = "https://platform.antares.id:8443/~/antares-cse/antares-id/Robot_smartdrawer/Lid_control";

WebServer server(80);

const int IN1A = 12, IN2A = 14, ENA = 13;
const int IN1B = 27, IN2B = 26, ENB = 25;
const int IN1C = 33, IN2C = 32, ENC = 15;

const int pwmChannelA = 0;
const int pwmChannelB = 1;
const int pwmChannelC = 2;

const int LED_BIRU_A = 4;
const int LED_MERAH_A = 5;
const int LED_BIRU_B = 16;
const int LED_MERAH_B = 17;
const int LED_BIRU_C = 18;
const int LED_MERAH_C = 19;

String last_laci_terbuka = "";
bool laci_terbuka = false;
String drawer_status_A = "CLOSED";
String drawer_status_B = "CLOSED";
String drawer_status_C = "CLOSED";
String last_activity = "";
bool wifi_connected = false;
String connection_mode = "Offline";

void setCORSHeaders() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With");
}

void handleOptions() {
  setCORSHeaders();
  server.send(200, "text/plain", "");
}

// === Enhanced WiFi Connection Function ===
bool connectToWiFi() {
  Serial.println("\n=== WiFi Connection Attempt ===");
  Serial.println("SSID: " + String(ssid));
  Serial.println("Signal Scan:");
  
  // Scan for available networks
  int n = WiFi.scanNetworks();
  bool ssid_found = false;
  
  for (int i = 0; i < n; ++i) {
    Serial.println("  " + String(i+1) + ": " + WiFi.SSID(i) + " (" + String(WiFi.RSSI(i)) + " dBm) " + 
                   (WiFi.encryptionType(i) == WIFI_AUTH_OPEN ? "Open" : "Encrypted"));
    if (WiFi.SSID(i) == ssid) {
      ssid_found = true;
      Serial.println("    ✅ Target SSID found with signal: " + String(WiFi.RSSI(i)) + " dBm");
    }
  }
  
  if (!ssid_found) {
    Serial.println("❌ Target SSID '" + String(ssid) + "' not found in scan!");
    return false;
  }

  // Try different WiFi modes
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  
  Serial.println("Attempting connection...");
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
    
    // Print current status
    if (attempts % 10 == 0) {
      Serial.println("\nStatus: " + String(WiFi.status()));
      Serial.println("Attempts: " + String(attempts) + "/20");
    }
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi Connected Successfully!");
    Serial.println("📡 Network: " + String(ssid));
    Serial.println("🌐 IP Address: " + WiFi.localIP().toString());
    Serial.println("📶 Signal Strength: " + String(WiFi.RSSI()) + " dBm");
    Serial.println("🔗 Gateway: " + WiFi.gatewayIP().toString());
    Serial.println("🔒 DNS: " + WiFi.dnsIP().toString());
    wifi_connected = true;
    connection_mode = "WiFi Station";
    return true;
  } else {
    Serial.println("\n❌ WiFi Connection Failed!");
    Serial.println("Status Code: " + String(WiFi.status()));
    wifi_connected = false;
    return false;
  }
}

// === Setup Access Point Mode ===
void setupAccessPoint() {
  Serial.println("\n=== Setting up Access Point Mode ===");
  
  WiFi.mode(WIFI_AP);
  bool ap_result = WiFi.softAP(ap_ssid, ap_password);
  
  if (ap_result) {
    Serial.println("✅ Access Point Created Successfully!");
    Serial.println("📡 AP SSID: " + String(ap_ssid));
    Serial.println("🔑 AP Password: " + String(ap_password));
    Serial.println("🌐 AP IP Address: " + WiFi.softAPIP().toString());
    Serial.println("📱 Connect to AP and access: http://" + WiFi.softAPIP().toString());
    connection_mode = "Access Point";
  } else {
    Serial.println("❌ Failed to create Access Point!");
    connection_mode = "Offline";
  }
}

// === HTML Web Interface (Updated) ===
const char* html_page = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Drawer Control</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255,255,255,0.95);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 2.5em;
        }
        .connection-status {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .connected {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .offline {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .ap-mode {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        .drawer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .drawer-card {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            border: 2px solid #e9ecef;
            transition: all 0.3s ease;
        }
        .drawer-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }
        .drawer-title {
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #495057;
        }
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            margin-bottom: 15px;
        }
        .status-open {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status-closed {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            font-weight: bold;
            margin: 5px;
            min-width: 80px;
            transition: all 0.3s ease;
        }
        .btn-open {
            background: #28a745;
            color: white;
        }
        .btn-open:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        .btn-close {
            background: #dc3545;
            color: white;
        }
        .btn-close:hover {
            background: #c82333;
            transform: translateY(-2px);
        }
        .btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
        }
        .system-status {
            background: #e3f2fd;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .status-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #2196f3;
        }
        .status-label {
            font-weight: bold;
            color: #666;
            font-size: 0.9em;
        }
        .status-value {
            font-size: 1.1em;
            color: #333;
            margin-top: 5px;
        }
        .loading {
            opacity: 0.6;
            pointer-events: none;
        }
        .wifi-debug {
            background: #f0f0f0;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            font-family: monospace;
            font-size: 0.9em;
        }
        @media (max-width: 768px) {
            .container {
                padding: 15px;
            }
            h1 {
                font-size: 2em;
            }
            .drawer-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗄️ Smart Drawer Control System</h1>
        
        <div class="connection-status" id="connectionStatus">
            📡 Checking connection...
        </div>
        
        <div class="drawer-grid">
            <div class="drawer-card">
                <div class="drawer-title">Drawer A</div>
                <div class="status-badge status-closed" id="statusA">CLOSED</div>
                <div>
                    <button class="btn btn-open" onclick="controlDrawer('A', 'open')">OPEN</button>
                    <button class="btn btn-close" onclick="controlDrawer('A', 'close')">CLOSE</button>
                </div>
            </div>
            
            <div class="drawer-card">
                <div class="drawer-title">Drawer B</div>
                <div class="status-badge status-closed" id="statusB">CLOSED</div>
                <div>
                    <button class="btn btn-open" onclick="controlDrawer('B', 'open')">OPEN</button>
                    <button class="btn btn-close" onclick="controlDrawer('B', 'close')">CLOSE</button>
                </div>
            </div>
            
            <div class="drawer-card">
                <div class="drawer-title">Drawer C</div>
                <div class="status-badge status-closed" id="statusC">CLOSED</div>
                <div>
                    <button class="btn btn-open" onclick="controlDrawer('C', 'open')">OPEN</button>
                    <button class="btn btn-close" onclick="controlDrawer('C', 'close')">CLOSE</button>
                </div>
            </div>
        </div>
        
        <div class="system-status">
            <h3>📊 System Status</h3>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">Connection Mode</div>
                    <div class="status-value" id="connectionMode">Checking...</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Last Activity</div>
                    <div class="status-value" id="lastActivity">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">ESP32 Status</div>
                    <div class="status-value" style="color: #28a745;">✅ Active</div>
                </div>
                <div class="status-item">
                    <div class="status-label">System Time</div>
                    <div class="status-value" id="systemTime">-</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Update status display
        function updateStatus(drawer, status) {
            const statusElement = document.getElementById('status' + drawer);
            statusElement.textContent = status;
            statusElement.className = 'status-badge ' + (status === 'OPEN' ? 'status-open' : 'status-closed');
        }

        // Update connection status
        function updateConnectionStatus(mode, wifi_connected) {
            const statusElement = document.getElementById('connectionStatus');
            const modeElement = document.getElementById('connectionMode');
            
            if (wifi_connected) {
                statusElement.className = 'connection-status connected';
                statusElement.innerHTML = '✅ WiFi Connected - IP: ' + window.location.hostname;
            } else if (mode === 'Access Point') {
                statusElement.className = 'connection-status ap-mode';
                statusElement.innerHTML = '📡 Access Point Mode - IP: ' + window.location.hostname;
            } else {
                statusElement.className = 'connection-status offline';
                statusElement.innerHTML = '⚠️ Offline Mode - Local Control Only';
            }
            
            modeElement.textContent = mode;
        }

        // Control drawer function
        async function controlDrawer(laci, aksi) {
            const container = document.querySelector('.container');
            container.classList.add('loading');
            
            try {
                const response = await fetch('/control', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        laci: laci,
                        aksi: aksi
                    })
                });
                
                const result = await response.json();
                console.log('Response:', result);
                
                if (result.status === 'OK') {
                    updateStatus(laci, aksi === 'open' ? 'OPEN' : 'CLOSED');
                    document.getElementById('lastActivity').textContent = new Date().toLocaleString();
                    alert(`Drawer ${laci} ${aksi === 'open' ? 'opened' : 'closed'} successfully!`);
                } else if (result.status === 'ignored') {
                    alert(result.reason);
                } else {
                    alert('Error: ' + (result.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Connection error. Please check ESP32 connection.');
            }
            
            container.classList.remove('loading');
        }

        // Update system time
        function updateSystemTime() {
            document.getElementById('systemTime').textContent = new Date().toLocaleString();
        }

        // Auto-refresh status every 5 seconds
        async function refreshStatus() {
            try {
                const response = await fetch('/status');
                const status = await response.json();
                
                updateStatus('A', status.drawer_A);
                updateStatus('B', status.drawer_B);
                updateStatus('C', status.drawer_C);
                updateConnectionStatus(status.connection_mode, status.wifi_connected);
                
                if (status.last_activity) {
                    document.getElementById('lastActivity').textContent = status.last_activity;
                }
            } catch (error) {
                console.error('Status refresh error:', error);
                updateConnectionStatus('Unknown', false);
            }
        }

        // Initialize
        updateSystemTime();
        setInterval(updateSystemTime, 1000);
        setInterval(refreshStatus, 5000);
        
        // Initial status refresh
        setTimeout(refreshStatus, 1000);
    </script>
</body>x
</html>
)rawliteral";

// === Kirim ke Antares (dengan error handling yang lebih baik) ===
void kirimKeAntares(String laci, String status, String user) {
  if (!wifi_connected) {
    Serial.println("WiFi tidak terhubung, skip kirim ke Antares");
    return;
  }
  
  HTTPClient http;
  http.begin(antares_url);
  http.addHeader("X-M2M-Origin", antares_api_key);
  http.addHeader("Content-Type", "application/json;ty=4");
  http.setTimeout(10000); // 10 second timeout
  
  String conPayload = "{\"laci\":\"" + laci + "\",\"status\":\"" + status + "\",\"user\":\"" + user + "\"}";
  conPayload.replace("\"", "\\\"");
  String fullPayload = "{\"m2m:cin\": {\"con\": \"" + conPayload + "\", \"cnf\": \"application/json\", \"lbl\": [\"esp32\"]}}";
  
  Serial.println("Mengirim ke Antares:");
  Serial.println(fullPayload);
  
  int responseCode = http.POST(fullPayload);
  String response = http.getString();
  
  Serial.println("Response Code: " + String(responseCode));
  Serial.println("Response: " + response);
  
  if (responseCode > 0 && responseCode < 400) {
    Serial.println("✅ Data berhasil dikirim ke Antares");
  } else {
    Serial.println("❌ Gagal kirim data ke Antares");
  }
  
  http.end();
}


void updateLED(String laci, bool buka) {
  if (laci == "A") {
    digitalWrite(LED_BIRU_A, buka ? HIGH : LOW);
    digitalWrite(LED_MERAH_A, buka ? LOW : HIGH);
  } else if (laci == "B") {
    digitalWrite(LED_BIRU_B, buka ? HIGH : LOW);
    digitalWrite(LED_MERAH_B, buka ? LOW : HIGH);
  } else if (laci == "C") {
    digitalWrite(LED_BIRU_C, buka ? HIGH : LOW);
    digitalWrite(LED_MERAH_C, buka ? LOW : HIGH);
  }
}

// === Motor Control Functions (unchanged) ===
void bukaLaci(String laci) {
  Serial.println("Membuka laci " + laci);
  last_activity = "Opening drawer " + laci + " at " + String(millis()/1000) + "s";
  
  if (laci == "A") {
    digitalWrite(IN1A, HIGH); digitalWrite(IN2A, LOW);
    ledcWrite(pwmChannelA, 200); delay(5000); ledcWrite(pwmChannelA, 0);
    drawer_status_A = "OPEN";
  } else if (laci == "B") {
    digitalWrite(IN1B, HIGH); digitalWrite(IN2B, LOW);
    ledcWrite(pwmChannelB, 200); delay(5000); ledcWrite(pwmChannelB, 0);
    drawer_status_B = "OPEN";
  } else if (laci == "C") {
    digitalWrite(IN1C, HIGH); digitalWrite(IN2C, LOW);
    ledcWrite(pwmChannelC, 200); delay(5000); ledcWrite(pwmChannelC, 0);
    drawer_status_C = "OPEN";
  }
  
  laci_terbuka = true;
  last_laci_terbuka = laci;
  updateLED(laci, true);
  kirimKeAntares(laci, "terbuka", "staf");
}


void tutupLaci(String laci) {
  Serial.println("Menutup laci " + laci);
  last_activity = "Closing drawer " + laci + " at " + String(millis()/1000) + "s";
  
  if (laci == "A") {
    digitalWrite(IN1A, LOW); digitalWrite(IN2A, HIGH);
    ledcWrite(pwmChannelA, 200); delay(5000); ledcWrite(pwmChannelA, 0);
    drawer_status_A = "CLOSED";
  } else if (laci == "B") {
    digitalWrite(IN1B, LOW); digitalWrite(IN2B, HIGH);
    ledcWrite(pwmChannelB, 200); delay(5000); ledcWrite(pwmChannelB, 0);
    drawer_status_B = "CLOSED";
  } else if (laci == "C") {
    digitalWrite(IN1C, LOW); digitalWrite(IN2C, HIGH);
    ledcWrite(pwmChannelC, 200); delay(5000); ledcWrite(pwmChannelC, 0);
    drawer_status_C = "CLOSED";
  }
  
  if (last_laci_terbuka == laci) {
    laci_terbuka = false;
    last_laci_terbuka = "";
  }
  updateLED(laci, false); 
  kirimKeAntares(laci, "tertutup", "staf");
}


// === Web Handlers ===
void handleRoot() {
  setCORSHeaders();
  server.send(200, "text/html", html_page);
}

void handleStatus() {
  setCORSHeaders();
  JsonDocument doc;
  doc["drawer_A"] = drawer_status_A;
  doc["drawer_B"] = drawer_status_B;
  doc["drawer_C"] = drawer_status_C;
  doc["last_activity"] = last_activity;
  doc["esp32_connected"] = true;
  doc["system_time"] = millis();
  doc["wifi_connected"] = wifi_connected;
  doc["connection_mode"] = connection_mode;
  
  if (wifi_connected) {
    doc["wifi_ip"] = WiFi.localIP().toString();
    doc["signal_strength"] = WiFi.RSSI();
  } else if (connection_mode == "Access Point") {
    doc["wifi_ip"] = WiFi.softAPIP().toString();
    doc["signal_strength"] = 0;
  }
  
  String jsonResponse;
  serializeJson(doc, jsonResponse);
  
  server.send(200, "application/json", jsonResponse);
}


void handleControl() {
  setCORSHeaders();
  
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, body);
    
    Serial.println("Received request body: " + body);
    
    if (error) {
      Serial.println("JSON Parse Error: " + String(error.c_str()));
      server.send(400, "application/json", "{\"error\":\"Invalid JSON\", \"details\":\"" + String(error.c_str()) + "\"}");
      return;
    }
    
    String laci = doc["laci"];
    String aksi = doc["aksi"];
    
    Serial.println("Dapat perintah: laci=" + laci + ", aksi=" + aksi);
    
    // Validate input
    if (laci != "A" && laci != "B" && laci != "C") {
      server.send(400, "application/json", "{\"error\":\"Invalid laci. Must be A, B, or C\"}");
      return;
    }
    
    if (aksi != "open" && aksi != "close") {
      server.send(400, "application/json", "{\"error\":\"Invalid aksi. Must be open or close\"}");
      return;
    }
    
    // Check current status
    String currentStatus = "";
    if (laci == "A") currentStatus = drawer_status_A;
    else if (laci == "B") currentStatus = drawer_status_B;
    else if (laci == "C") currentStatus = drawer_status_C;
    
    if (aksi == "open") {
      if (currentStatus == "OPEN") {
        Serial.println("Laci " + laci + " sudah terbuka, abaikan perintah.");
        server.send(200, "application/json", "{\"status\":\"ignored\", \"reason\":\"Laci " + laci + " sudah terbuka\"}");
        return;
      }
      bukaLaci(laci);
    } else if (aksi == "close") {
      if (currentStatus == "CLOSED") {
        Serial.println("Laci " + laci + " sudah tertutup, abaikan perintah.");
        server.send(200, "application/json", "{\"status\":\"ignored\", \"reason\":\"Laci " + laci + " sudah tertutup\"}");
        return;
      }
      tutupLaci(laci);
    }
    
    // Send success response
    JsonDocument responseDoc;
    responseDoc["status"] = "OK";
    responseDoc["laci"] = laci;
    responseDoc["aksi"] = aksi;
    responseDoc["new_status"] = (aksi == "open") ? "OPEN" : "CLOSED";
    responseDoc["timestamp"] = millis();
    responseDoc["wifi_connected"] = wifi_connected;
    
    String jsonResponse;
    serializeJson(responseDoc, jsonResponse);
    
    server.send(200, "application/json", jsonResponse);
    
  } else {
    server.send(400, "application/json", "{\"error\":\"No data received\"}");
  }
}

void handleNotFound() {
  setCORSHeaders();
  server.send(404, "text/plain", "404 Not Found\n\nAvailable endpoints:\n/ - Web Interface\n/status - System Status\n/control - Control API");
}

void setupPWM() {
  ledcSetup(pwmChannelA, 1000, 8); ledcAttachPin(ENA, pwmChannelA);
  ledcSetup(pwmChannelB, 1000, 8); ledcAttachPin(ENB, pwmChannelB);
  ledcSetup(pwmChannelC, 1000, 8); ledcAttachPin(ENC, pwmChannelC);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=== Smart Drawer System Starting ===");
  
  // Initialize pins
  pinMode(IN1A, OUTPUT); pinMode(IN2A, OUTPUT);
  pinMode(IN1B, OUTPUT); pinMode(IN2B, OUTPUT);
  pinMode(IN1C, OUTPUT); pinMode(IN2C, OUTPUT);
  pinMode(LED_BIRU_A, OUTPUT); pinMode(LED_MERAH_A, OUTPUT);
  pinMode(LED_BIRU_B, OUTPUT); pinMode(LED_MERAH_B, OUTPUT);
  pinMode(LED_BIRU_C, OUTPUT); pinMode(LED_MERAH_C, OUTPUT);
  updateLED("A", false); updateLED("B", false); updateLED("C", false);
  setupPWM();

  // Ensure all motors are stopped initially
  digitalWrite(IN1A, LOW); digitalWrite(IN2A, LOW);
  digitalWrite(IN1B, LOW); digitalWrite(IN2B, LOW);
  digitalWrite(IN1C, LOW); digitalWrite(IN2C, LOW);
  
  setupPWM();
  
  // Try to connect to WiFi
  if (!connectToWiFi()) {
    Serial.println("\n⚠️ WiFi connection failed, setting up Access Point...");
    setupAccessPoint();
  }

   // Setup web server routes
  server.on("/", HTTP_GET, handleRoot);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/control", HTTP_POST, handleControl);
  server.on("/control", HTTP_OPTIONS, handleOptions);
  server.onNotFound(handleNotFound);
  
  // Start server
  server.begin();
  Serial.println("🚀 HTTP Server Started on Port 80");
  
  if (wifi_connected) {
    Serial.println("🌐 Access web interface at: http://" + WiFi.localIP().toString());
  } else if (connection_mode == "Access Point") {
    Serial.println("🌐 Access web interface at: http://" + WiFi.softAPIP().toString());
  }
  
  Serial.println("=== Smart Drawer System Ready ===");
  Serial.println("Connection Mode: " + connection_mode);
  Serial.println("Drawer Status: A=" + drawer_status_A + " B=" + drawer_status_B + " C=" + drawer_status_C);
}

void loop() {
  server.handleClient();
  
  // Check WiFi connection periodically (only if not in AP mode)
  static unsigned long lastWiFiCheck = 0;
  if (connection_mode != "Access Point" && millis() - lastWiFiCheck > 30000) {
    if (WiFi.status() != WL_CONNECTED && wifi_connected) {
      Serial.println("⚠️ WiFi connection lost. Attempting to reconnect...");
      wifi_connected = false;
      connection_mode = "Offline";
      
      if (connectToWiFi()) {
        Serial.println("✅ WiFi reconnected successfully!");
      } else {
        Serial.println("❌ WiFi reconnection failed, switching to AP mode...");
        setupAccessPoint();
      }
    }
    lastWiFiCheck = millis();
  }
  
  delay(10);
}