#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#define IRAM_ATTR
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define RISING 3
inline int digitalRead(int){return 0;} inline void digitalWrite(int,int){} inline void pinMode(int,int){} inline void analogWrite(int,int){}
inline uint32_t millis(){return 0;} inline uint32_t micros(){return 0;}
inline int digitalPinToInterrupt(int p){return p;} inline void attachInterrupt(int, void(*)(), int){}
struct S{ void begin(int){} int available(){return 0;} int read(){return -1;}
 template<class...A> int printf(const char*f,A...a){return ::printf(f,a...);} void println(const char*s=""){puts(s);} void print(const char*s){fputs(s,stdout);} };
static S Serial;
