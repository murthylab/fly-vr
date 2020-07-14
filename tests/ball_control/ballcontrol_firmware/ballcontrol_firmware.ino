#include <Stepper.h>
 
int in1Pin = 12;
int in2Pin = 11;
int in3Pin = 10;
int in4Pin = 9;

#define DEBUG_CMD 1

#define STEPS 5
int steps;

Stepper motor(512, in1Pin, in2Pin, in3Pin, in4Pin);  

void help()
{
  Serial.println("Single char protocol. '0' = Stop, '1' = 5RPM, ... '8' = 40 RPM, etc");
}
 
void setup()
{
  pinMode(in1Pin, OUTPUT);
  pinMode(in2Pin, OUTPUT);
  pinMode(in3Pin, OUTPUT);
  pinMode(in4Pin, OUTPUT);

  Serial.begin(57600);
  while (!Serial) {
    ;
  }

  // start motor stationary
  steps = 0;

  // If I uncomment the following code the code hangs at this point.  
  // 
  // This is not mentioned in the documentation. It's
  // hard to believe I am the first person to encounter this problem, so I
  // will just assume the quality of arduino standard libraries (v 1.8.13)
  // remains _terrible_
  //
  // motor.setSpeed(0);

  help();

}
 
void loop()
{
  // simple single ascii character protocol '0' = stop
  // 1 - 8 -> 5 - 40 RPM
  // only step if we have speed != 0

  if (Serial.available()) {
    int ch = Serial.read();
  
    if (ch != -1) {
      ch = ch - '0';
  
      if (ch == 0) {
        steps = 0;
        #if DEBUG_CMD
          Serial.println("RPM=0");
        #endif
      } else if ((ch <= 8) && (ch > 0)) {
        motor.setSpeed(ch * 5);
        steps = STEPS;
        #if DEBUG_CMD
          Serial.print("RPM=");
          Serial.println(ch * 5);
        #endif
      } else {
        help();
      }
    }

  }

  if (steps) {
    motor.step(steps);
  }

}
