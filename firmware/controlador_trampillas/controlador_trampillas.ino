/*
  Controlador de trampillas · ESP32 (framework Arduino)

  Este programa NO decide qué fruta es mala. Solo:
    1. cuenta el avance de la cinta con el encoder,
    2. dispara la cámara cada N cuentas (opcional) y avisa al PC,
    3. guarda las órdenes de expulsión que le manda el software de detección,
    4. abre la trampilla de cada carril cuando la fruta marcada pasa por encima,
    5. para la cinta y cierra todo si el PC deja de dar señales de vida,
    6. en modo MANUAL ignora al detector y obedece solo al panel (mecánicos).

  Comunicación: líneas de texto por USB-serie a 115200 baudios.
  El protocolo completo está en docs/protocolo.md.
*/
#include <Arduino.h>

// ---------------- Pines (ajústalos a tu montaje) ----------------
const int PIN_ENC_A   = 34;   // encoder canal A (solo entrada, necesita pull-up externo)
const int PIN_ENC_B   = 35;   // encoder canal B
const int PIN_DISPARO = 25;   // disparo hardware de la cámara (a su entrada de trigger)
const int PIN_CINTA   = 26;   // relé o entrada de marcha del variador
const int PIN_VELOCIDAD = 27; // PWM -> convertidor 0-10 V -> consigna de velocidad del variador
const int N_CARRILES  = 4;
const int PIN_TRAMPILLA[N_CARRILES] = {16, 17, 18, 19};  // a los drivers de las electroválvulas

// ---------------- Configuración (se cambia desde el PC con SET) ----------------
int32_t  offsetCarril[N_CARRILES] = {3000, 3000, 3000, 3000}; // cuentas de la línea de referencia de la cámara al centro de la trampilla
int32_t  preCuentas   = 40;    // abrir este número de cuentas antes de que llegue el centro de la fruta
int32_t  postCuentas  = 60;    // cerrar este número de cuentas después
uint32_t maxAbiertaMs = 1500;  // seguridad: tiempo máximo con una trampilla abierta
uint32_t cadaDisparo  = 0;     // 0 = sin disparo hardware; si no, disparar cada N cuentas
uint32_t watchdogMs   = 500;   // sin PING durante este tiempo -> parada segura
const uint32_t ENVIO_CUENTA_MS = 20;   // cada cuánto se envía la cuenta al PC
const uint32_t PULSO_DISPARO_US = 500; // duración del pulso de disparo de la cámara
const uint32_t PRUEBA_MS = 300;        // apertura de prueba (orden TEST)
const uint32_t MANUAL_MAX_MS = 10000;  // en manual, una trampilla abierta se cierra sola a los 10 s

// ---------------- Encoder ----------------
volatile uint32_t cuenta = 0;   // 32 bits: la lectura es atómica en el ESP32

void IRAM_ATTR isrEncoder() {
  if (digitalRead(PIN_ENC_B)) cuenta--; else cuenta++;
}

// Diferencia con signo entre dos cuentas; funciona aunque el contador dé la vuelta.
inline int32_t dif(uint32_t a, uint32_t b) { return (int32_t)(a - b); }

// ---------------- Órdenes de expulsión ----------------
struct Orden {
  bool     usada;
  bool     abierta;  // ya ha empezado su ventana de apertura
  uint32_t id;
  uint32_t abrir;    // cuenta a la que se abre
  uint32_t cerrar;   // cuenta a la que se cierra
};
const int MAX_ORDENES = 24;
Orden ordenes[N_CARRILES][MAX_ORDENES];

bool     trampillaAbierta[N_CARRILES];
uint32_t abiertaDesdeMs[N_CARRILES];
uint32_t pruebaHastaMs[N_CARRILES];
bool     manualAbierta[N_CARRILES];   // trampillas abiertas a mano desde el panel

// ---------------- Estado general ----------------
bool     enMarcha = false;
bool     modoManual = false;
int      velocidadPct = 50;
uint32_t ultimoPingMs = 0;
uint32_t ultimoEnvioMs = 0;
uint32_t numFoto = 0;
uint32_t proximoDisparo = 0;
bool     disparoActivo = false;
uint32_t disparoDesdeUs = 0;

char     linea[96];
uint8_t  largo = 0;

// ---------------- Utilidades ----------------
void ponerTrampilla(int c, bool abrir) {
  if (abrir == trampillaAbierta[c]) return;
  trampillaAbierta[c] = abrir;
  digitalWrite(PIN_TRAMPILLA[c], abrir ? HIGH : LOW);
  if (abrir) abiertaDesdeMs[c] = millis();
  Serial.printf("D %d %d\n", c, abrir ? 1 : 0);   // avisar al panel
}

void ponerVelocidad(int pct) {
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  velocidadPct = pct;
  analogWrite(PIN_VELOCIDAD, pct * 255 / 100);
}

void borrarOrdenes() {
  for (int c = 0; c < N_CARRILES; c++)
    for (int i = 0; i < MAX_ORDENES; i++) ordenes[c][i].usada = false;
}

void pararCinta() {
  enMarcha = false;
  digitalWrite(PIN_CINTA, LOW);
}

void paradaSegura(const char *motivo) {
  pararCinta();
  borrarOrdenes();
  for (int c = 0; c < N_CARRILES; c++) { pruebaHastaMs[c] = 0; manualAbierta[c] = false; ponerTrampilla(c, false); }
  Serial.printf("ERR %s\n", motivo);
}

// ---------------- Orden EJ: expulsar una fruta ----------------
void ordenExpulsar(uint32_t id, int carril, uint32_t cuentaRef) {
  if (carril < 0 || carril >= N_CARRILES) { Serial.printf("ERR CARRIL %lu\n", (unsigned long)id); return; }
  if (modoManual) { Serial.printf("ERR MANUAL %lu\n", (unsigned long)id); return; }  // el mecánico manda

  uint32_t centro = cuentaRef + (uint32_t)offsetCarril[carril];
  uint32_t abrir  = centro - (uint32_t)preCuentas;
  uint32_t cerrar = centro + (uint32_t)postCuentas;
  uint32_t ahora  = cuenta;

  // Si la fruta ya ha pasado la trampilla, no se puede hacer nada: avisar al PC.
  if (dif(cerrar, ahora) <= 0) { Serial.printf("LATE %lu\n", (unsigned long)id); return; }

  // Si se solapa con otra orden del mismo carril (la misma fruta vista en dos fotos), se fusionan.
  for (int i = 0; i < MAX_ORDENES; i++) {
    Orden &o = ordenes[carril][i];
    if (!o.usada) continue;
    if (dif(abrir, o.cerrar) <= 0 && dif(o.abrir, cerrar) <= 0) {
      if (dif(abrir, o.abrir) < 0)   o.abrir = abrir;
      if (dif(cerrar, o.cerrar) > 0) o.cerrar = cerrar;
      Serial.printf("ACK %lu %lu\n", (unsigned long)id, (unsigned long)o.id);  // fusionada con o.id
      return;
    }
  }
  for (int i = 0; i < MAX_ORDENES; i++) {
    Orden &o = ordenes[carril][i];
    if (o.usada) continue;
    o.usada = true; o.abierta = false; o.id = id; o.abrir = abrir; o.cerrar = cerrar;
    Serial.printf("ACK %lu\n", (unsigned long)id);
    return;
  }
  Serial.printf("FULL %lu\n", (unsigned long)id);
}

// ---------------- Lectura de órdenes del PC ----------------
void procesarLinea(char *s) {
  char *cmd = strtok(s, " ");
  if (!cmd) return;

  if (!strcmp(cmd, "PING")) {
    ultimoPingMs = millis();
    Serial.printf("PONG %lu\n", (unsigned long)cuenta);

  } else if (!strcmp(cmd, "EJ")) {           // EJ <id> <carril> <cuenta_referencia>
    char *a = strtok(NULL, " "), *b = strtok(NULL, " "), *c = strtok(NULL, " ");
    if (!a || !b || !c) { Serial.println("ERR SINTAXIS EJ"); return; }
    ordenExpulsar(strtoul(a, NULL, 10), atoi(b), strtoul(c, NULL, 10));

  } else if (!strcmp(cmd, "RUN")) {          // RUN 1 | RUN 0
    char *a = strtok(NULL, " ");
    if (a && atoi(a) == 1) {
      if (millis() - ultimoPingMs > watchdogMs) { Serial.println("ERR SIN_PING"); return; }
      enMarcha = true; digitalWrite(PIN_CINTA, HIGH);
      proximoDisparo = cuenta + cadaDisparo;
    } else {
      pararCinta();
    }
    Serial.println("OK");

  } else if (!strcmp(cmd, "SET")) {          // SET <clave> [carril] <valor>
    char *k = strtok(NULL, " "), *a = strtok(NULL, " "), *b = strtok(NULL, " ");
    if (!k || !a) { Serial.println("ERR SINTAXIS SET"); return; }
    if (!strcmp(k, "OFFSET")) {
      int c = atoi(a);
      if (!b || c < 0 || c >= N_CARRILES) { Serial.println("ERR SINTAXIS SET"); return; }
      offsetCarril[c] = atol(b);
    }
    else if (!strcmp(k, "PRE"))   preCuentas = atol(a);
    else if (!strcmp(k, "POST"))  postCuentas = atol(a);
    else if (!strcmp(k, "MAXMS")) maxAbiertaMs = strtoul(a, NULL, 10);
    else if (!strcmp(k, "TRIG"))  { cadaDisparo = strtoul(a, NULL, 10); proximoDisparo = cuenta + cadaDisparo; }
    else if (!strcmp(k, "WD"))    watchdogMs = strtoul(a, NULL, 10);
    else { Serial.println("ERR CLAVE"); return; }
    Serial.println("OK");

  } else if (!strcmp(cmd, "TEST")) {         // TEST <carril>: abre la trampilla un momento
    char *a = strtok(NULL, " ");
    int c = a ? atoi(a) : -1;
    if (c < 0 || c >= N_CARRILES) { Serial.println("ERR CARRIL"); return; }
    pruebaHastaMs[c] = millis() + PRUEBA_MS;
    Serial.println("OK");

  } else if (!strcmp(cmd, "MODE")) {         // MODE AUTO | MODE MAN
    char *a = strtok(NULL, " ");
    if (!a) { Serial.println("ERR SINTAXIS MODE"); return; }
    if (!strcmp(a, "MAN")) {
      pararCinta();                           // al pasar a manual, la cinta se para
      borrarOrdenes();
      modoManual = true;
    } else if (!strcmp(a, "AUTO")) {
      pararCinta();
      for (int c = 0; c < N_CARRILES; c++) { manualAbierta[c] = false; pruebaHastaMs[c] = 0; }
      modoManual = false;
    } else { Serial.println("ERR SINTAXIS MODE"); return; }
    Serial.println("OK");

  } else if (!strcmp(cmd, "DOOR")) {         // DOOR <carril> <1|0>: solo en manual
    char *a = strtok(NULL, " "), *b = strtok(NULL, " ");
    int c = a ? atoi(a) : -1;
    if (!modoManual) { Serial.println("ERR NO_MANUAL"); return; }
    if (!b || c < 0 || c >= N_CARRILES) { Serial.println("ERR CARRIL"); return; }
    manualAbierta[c] = atoi(b) == 1;
    Serial.println("OK");

  } else if (!strcmp(cmd, "SPEED")) {        // SPEED <0-100>: consigna de velocidad en %
    char *a = strtok(NULL, " ");
    if (!a) { Serial.println("ERR SINTAXIS SPEED"); return; }
    ponerVelocidad(atoi(a));
    Serial.println("OK");

  } else if (!strcmp(cmd, "CLEAR")) {
    borrarOrdenes();
    Serial.println("OK");

  } else if (!strcmp(cmd, "ST")) {
    Serial.printf("ST run=%d cuenta=%lu modo=%s v=%d q=", enMarcha ? 1 : 0, (unsigned long)cuenta,
                  modoManual ? "MAN" : "AUTO", velocidadPct);
    for (int c = 0; c < N_CARRILES; c++) {
      int n = 0;
      for (int i = 0; i < MAX_ORDENES; i++) if (ordenes[c][i].usada) n++;
      Serial.printf(c ? ",%d" : "%d", n);
    }
    Serial.print(" d=");
    for (int c = 0; c < N_CARRILES; c++) Serial.print(trampillaAbierta[c] ? "1" : "0");
    Serial.println();

  } else {
    Serial.println("ERR ORDEN");
  }
}

void leerSerie() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') { linea[largo] = 0; if (largo) procesarLinea(linea); largo = 0; }
    else if (largo < sizeof(linea) - 1) linea[largo++] = ch;
    else largo = 0;  // línea demasiado larga: se descarta
  }
}

// ---------------- Trampillas ----------------
void actualizarTrampillas() {
  uint32_t ahora = cuenta;
  uint32_t ms = millis();

  for (int c = 0; c < N_CARRILES; c++) {
    bool abrir = false;

    for (int i = 0; i < MAX_ORDENES; i++) {
      Orden &o = ordenes[c][i];
      if (!o.usada) continue;
      if (dif(ahora, o.cerrar) >= 0) {           // ventana terminada
        o.usada = false;
        Serial.printf("DONE %lu\n", (unsigned long)o.id);
        continue;
      }
      if (dif(ahora, o.abrir) >= 0) { abrir = true; o.abierta = true; }
    }

    if (pruebaHastaMs[c]) {
      if ((int32_t)(ms - pruebaHastaMs[c]) < 0) abrir = true; else pruebaHastaMs[c] = 0;
    }

    if (modoManual) {
      if (manualAbierta[c]) abrir = true;
      // En manual también hay límite: nadie deja una trampilla abierta y se va.
      if (abrir && trampillaAbierta[c] && ms - abiertaDesdeMs[c] > MANUAL_MAX_MS) {
        manualAbierta[c] = false; pruebaHastaMs[c] = 0; abrir = false;
        Serial.printf("ERR TIEMPO_MANUAL %d\n", c);
      }
      ponerTrampilla(c, abrir);
      continue;
    }

    // Seguridad: si la cinta se para con una trampilla abierta, no dejarla abierta indefinidamente.
    if (abrir && trampillaAbierta[c] && ms - abiertaDesdeMs[c] > maxAbiertaMs) {
      for (int i = 0; i < MAX_ORDENES; i++) {
        Orden &o = ordenes[c][i];
        if (o.usada && o.abierta) { o.usada = false; Serial.printf("ERR TIEMPO %lu\n", (unsigned long)o.id); }
      }
      pruebaHastaMs[c] = 0;
      abrir = false;
    }

    ponerTrampilla(c, abrir);
  }
}

// ---------------- Disparo de la cámara ----------------
void actualizarDisparo() {
  uint32_t ahora = cuenta;
  if (disparoActivo && micros() - disparoDesdeUs >= PULSO_DISPARO_US) {
    digitalWrite(PIN_DISPARO, LOW);
    disparoActivo = false;
  }
  if (!enMarcha || cadaDisparo == 0 || disparoActivo) return;
  if (dif(ahora, proximoDisparo) >= 0) {
    digitalWrite(PIN_DISPARO, HIGH);
    disparoActivo = true;
    disparoDesdeUs = micros();
    numFoto++;
    Serial.printf("F %lu %lu\n", (unsigned long)numFoto, (unsigned long)ahora);
    proximoDisparo += cadaDisparo;
    if (dif(ahora, proximoDisparo) >= 0) proximoDisparo = ahora + cadaDisparo;  // por si se han saltado disparos
  }
}

// ---------------- Arranque y bucle ----------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_ENC_A, INPUT);
  pinMode(PIN_ENC_B, INPUT);
  pinMode(PIN_DISPARO, OUTPUT); digitalWrite(PIN_DISPARO, LOW);
  pinMode(PIN_CINTA, OUTPUT);   digitalWrite(PIN_CINTA, LOW);
  pinMode(PIN_VELOCIDAD, OUTPUT);
  ponerVelocidad(velocidadPct);
  for (int c = 0; c < N_CARRILES; c++) {
    pinMode(PIN_TRAMPILLA[c], OUTPUT);
    digitalWrite(PIN_TRAMPILLA[c], LOW);
    trampillaAbierta[c] = false;
    pruebaHastaMs[c] = 0;
    manualAbierta[c] = false;
  }
  borrarOrdenes();
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), isrEncoder, RISING);
  Serial.println("READY triaje 1");
}

void loop() {
  leerSerie();

  if (enMarcha && millis() - ultimoPingMs > watchdogMs) paradaSegura("WATCHDOG");

  actualizarDisparo();
  actualizarTrampillas();

  if (millis() - ultimoEnvioMs >= ENVIO_CUENTA_MS) {
    ultimoEnvioMs = millis();
    Serial.printf("C %lu\n", (unsigned long)cuenta);
  }
}
