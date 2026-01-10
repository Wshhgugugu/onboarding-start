# ASIC Onboarding Project - Shiheng

## Description

SPI-controlled PWM peripheral for Tiny Tapeout.

## Features

- SPI interface for register configuration
- 16-channel PWM output
- Configurable duty cycle

## Register Map

| Address | Name | Description |
|---------|------|-------------|
| 0x00 | EN_REG_OUT_7_0 | Output enable for channels 0-7 |
| 0x01 | EN_REG_OUT_15_8 | Output enable for channels 8-15 |
| 0x02 | EN_REG_PWM_7_0 | PWM enable for channels 0-7 |
| 0x03 | EN_REG_PWM_15_8 | PWM enable for channels 8-15 |
| 0x04 | PWM_DUTY_CYCLE | PWM duty cycle (0-255) |

## How to Use

1. Configure output enable registers
2. Configure PWM enable registers  
3. Set duty cycle
4. Outputs will generate PWM signals accordingly
