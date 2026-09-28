/*
  Arduino Nano Every - Geiger -> Duet Trigger

  Wiring:
    Geiger pulse/VIN -> Nano D2
    Geiger GND       -> Nano GND

    Nano D3          -> Duet io5.in
    Nano GND         -> Duet GND

  Duet:
    M558 K0 P5 C"^!io5.in" H5 F120 T6000
    G31 K0 P500

  Behaviour:

    - Geiger pulses detected on D2 using FALLING interrupt
    - Built-in LED flashes for every detected pulse

    - Pulses are counted during WINDOW_MS

    - If counts >= COUNT_THRESHOLD:
          Duet trigger ON

    - If counts < COUNT_THRESHOLD:
          Duet trigger OFF

    - No trigger delay / hold time
*/


// ======================================================
// Pins
// ======================================================

const byte GEIGER_PIN = 2;
const byte DUET_PIN   = 3;
const byte LED_PIN    = LED_BUILTIN;


// ======================================================
// SETTINGS
// ======================================================

// Counting period
const unsigned long WINDOW_MS = 50;

// Number of pulses required within WINDOW_MS
//
// Example:
// 1 = one pulse triggers
// 3 = three or more pulses trigger
// 4 = four or more pulses trigger
//
const unsigned int COUNT_THRESHOLD = 10;


// LED visible flash duration
const unsigned long LED_FLASH_MS = 50;


// Startup Duet test
const unsigned long STARTUP_TRIGGER_MS = 2000;


// ======================================================
// Interrupt variables
// ======================================================

volatile unsigned int pulseCount = 0;

volatile unsigned long totalPulseCount = 0;


// ======================================================
// Runtime variables
// ======================================================

unsigned long lastWindowTime = 0;

unsigned long lastSeenPulseCount = 0;


// LED
bool ledIsOn = false;
unsigned long ledStartTime = 0;


// Duet state
bool duetTriggered = false;


// ======================================================
// Duet open-drain output
// ======================================================

void duetRelease()
{
  /*
    D3 becomes high impedance.

    Duet's internal pull-up makes io5.in HIGH.

    With:
      C"^!io5.in"

    this corresponds to NOT triggered.
  */

  digitalWrite(DUET_PIN, LOW);

  pinMode(DUET_PIN, INPUT);
}


void duetTrigger()
{
  /*
    Pull Duet io5.in LOW.

    D3 is never driven HIGH.
  */

  digitalWrite(DUET_PIN, LOW);

  pinMode(DUET_PIN, OUTPUT);
}


// ======================================================
// Geiger interrupt
// ======================================================

void geigerISR()
{
  pulseCount++;

  totalPulseCount++;
}


// ======================================================
// Setup
// ======================================================

void setup()
{
  // ----------------------------------------------------
  // Geiger input
  // ----------------------------------------------------

  pinMode(GEIGER_PIN, INPUT);


  // ----------------------------------------------------
  // Built-in LED
  // ----------------------------------------------------

  pinMode(LED_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);


  // ----------------------------------------------------
  // Duet
  // ----------------------------------------------------

  duetRelease();


  // ====================================================
  // Startup LED test
  // ====================================================

  for (byte i = 0; i < 3; i++)
  {
    digitalWrite(LED_PIN, HIGH);
    delay(250);

    digitalWrite(LED_PIN, LOW);
    delay(250);
  }


  // ====================================================
  // Startup Duet test
  // ====================================================

  duetTrigger();

  delay(STARTUP_TRIGGER_MS);

  duetRelease();


  // ====================================================
  // Enable Geiger interrupt
  // ====================================================

  attachInterrupt(
    digitalPinToInterrupt(GEIGER_PIN),
    geigerISR,
    FALLING
  );


  lastWindowTime = millis();
}


// ======================================================
// Main loop
// ======================================================

void loop()
{
  unsigned long now = millis();


  // ====================================================
  // Check if new Geiger pulses occurred
  // ====================================================

  unsigned long totalNow;


  noInterrupts();

  totalNow = totalPulseCount;

  interrupts();


  if (totalNow != lastSeenPulseCount)
  {
    lastSeenPulseCount = totalNow;


    // --------------------------------------------------
    // Flash LED
    // --------------------------------------------------

    digitalWrite(LED_PIN, HIGH);

    ledIsOn = true;

    ledStartTime = now;
  }


  // ====================================================
  // Turn LED off
  // ====================================================

  if (ledIsOn &&
      (now - ledStartTime >= LED_FLASH_MS))
  {
    digitalWrite(LED_PIN, LOW);

    ledIsOn = false;
  }


  // ====================================================
  // Evaluate Geiger count every WINDOW_MS
  // ====================================================

  if (now - lastWindowTime >= WINDOW_MS)
  {
    unsigned int counts;


    // --------------------------------------------------
    // Safely copy/reset counter
    // --------------------------------------------------

    noInterrupts();

    counts = pulseCount;

    pulseCount = 0;

    interrupts();


    // ==================================================
    // THRESHOLD LOGIC
    // ==================================================

    if (counts >= COUNT_THRESHOLD)
    {
      // Above threshold
      // Keep Duet triggered

      duetTriggered = true;

      duetTrigger();
    }
    else
    {
      // Below threshold
      // Immediately release Duet

      duetTriggered = false;

      duetRelease();
    }


    // ==================================================
    // Start next measurement window
    // ==================================================

    lastWindowTime += WINDOW_MS;


    // Recover if execution somehow falls behind
    if (now - lastWindowTime >= WINDOW_MS)
    {
      lastWindowTime = now;
    }
  }
}