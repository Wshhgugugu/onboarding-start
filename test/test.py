import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles, Timer


async def reset_dut(dut):
    """Reset the DUT."""
    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0b00000100  # nCS idle high (bit 2)
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


async def spi_write(dut, address, data):
    """Send a 16-bit SPI write transaction: 1(R/W) + 7(addr) + 8(data)."""
    # Build 16-bit frame: R/W=1 (write), 7-bit address, 8-bit data
    frame = (1 << 15) | ((address & 0x7F) << 8) | (data & 0xFF)

    # Pull nCS low to start transaction
    ui_val = dut.ui_in.value & ~(1 << 2)  # Clear nCS (bit 2)
    dut.ui_in.value = int(ui_val)
    await ClockCycles(dut.clk, 5)

    # Shift out 16 bits, MSB first, SPI Mode 0
    for i in range(15, -1, -1):
        bit = (frame >> i) & 1

        # Set COPI (bit 1), SCLK low (bit 0)
        ui_val = int(dut.ui_in.value)
        ui_val = (ui_val & ~0x03)  # Clear SCLK and COPI
        ui_val = ui_val | (bit << 1)  # Set COPI
        dut.ui_in.value = ui_val
        await ClockCycles(dut.clk, 5)

        # SCLK rising edge - peripheral samples COPI here
        ui_val = int(dut.ui_in.value)
        ui_val = ui_val | 1  # Set SCLK high
        dut.ui_in.value = ui_val
        await ClockCycles(dut.clk, 5)

        # SCLK falling edge
        ui_val = int(dut.ui_in.value)
        ui_val = ui_val & ~1  # Set SCLK low
        dut.ui_in.value = ui_val
        await ClockCycles(dut.clk, 3)

    # Pull nCS high to end transaction
    await ClockCycles(dut.clk, 3)
    ui_val = int(dut.ui_in.value)
    ui_val = ui_val | (1 << 2)  # Set nCS high
    dut.ui_in.value = ui_val
    await ClockCycles(dut.clk, 20)  # Wait for transaction to be processed


async def measure_pwm(dut, bit_index, timeout_us=2000):
    """
    Measure PWM frequency and duty cycle on a specific uo_out bit.
    Returns (frequency_hz, duty_cycle_percent).
    """
    timeout_ns = timeout_us * 1000

    # Wait for first rising edge
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await RisingEdge(dut.clk)
        current = (int(dut.uo_out.value) >> bit_index) & 1
        elapsed = cocotb.utils.get_sim_time(units="ns") - start_time
        if current == 1:
            break
        if elapsed > timeout_ns:
            return None, 0.0  # Signal stuck low = 0% duty cycle

    # Record rising edge time
    t_rising_1 = cocotb.utils.get_sim_time(units="ns")

    # Wait for falling edge
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await RisingEdge(dut.clk)
        current = (int(dut.uo_out.value) >> bit_index) & 1
        elapsed = cocotb.utils.get_sim_time(units="ns") - start_time
        if current == 0:
            break
        if elapsed > timeout_ns:
            return None, 100.0  # Signal stuck high = 100% duty cycle

    t_falling = cocotb.utils.get_sim_time(units="ns")

    # Wait for second rising edge
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await RisingEdge(dut.clk)
        current = (int(dut.uo_out.value) >> bit_index) & 1
        elapsed = cocotb.utils.get_sim_time(units="ns") - start_time
        if current == 1:
            break
        if elapsed > timeout_ns:
            return None, None

    t_rising_2 = cocotb.utils.get_sim_time(units="ns")

    period_ns = t_rising_2 - t_rising_1
    high_time_ns = t_falling - t_rising_1
    frequency = 1e9 / period_ns
    duty_cycle = (high_time_ns / period_ns) * 100.0

    return frequency, duty_cycle


@cocotb.test()
async def test_pwm_50_percent(dut):
    """Test PWM with 50% duty cycle."""
    clock = Clock(dut.clk, 100, units="ns")  # 10 MHz
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Enable output on uo_out[0] (register 0x00)
    await spi_write(dut, 0x00, 0x01)
    # Enable PWM mode on uo_out[0] (register 0x02)
    await spi_write(dut, 0x02, 0x01)
    # Set duty cycle to 50% = 128/256 (register 0x04)
    await spi_write(dut, 0x04, 128)

    # Wait for PWM to stabilize
    await ClockCycles(dut.clk, 1000)

    freq, duty = await measure_pwm(dut, 0)

    dut._log.info(f"50% test - Frequency: {freq:.1f} Hz, Duty Cycle: {duty:.1f}%")

    assert freq is not None, "PWM signal not toggling"
    assert 2970 <= freq <= 3030, f"Frequency {freq:.1f} Hz out of range (2970-3030)"
    assert 49.0 <= duty <= 51.0, f"Duty cycle {duty:.1f}% out of range (49-51)"


@cocotb.test()
async def test_pwm_0_percent(dut):
    """Test PWM with 0% duty cycle (always low)."""
    clock = Clock(dut.clk, 100, units="ns")  # 10 MHz
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Enable output on uo_out[0]
    await spi_write(dut, 0x00, 0x01)
    # Enable PWM mode on uo_out[0]
    await spi_write(dut, 0x02, 0x01)
    # Set duty cycle to 0%
    await spi_write(dut, 0x04, 0)

    await ClockCycles(dut.clk, 5000)

    # At 0% duty cycle the signal should stay low
    freq, duty = await measure_pwm(dut, 0, timeout_us=1000)

    dut._log.info(f"0% test - Frequency: {freq}, Duty Cycle: {duty}%")

    assert duty == 0.0 or freq is None, "Signal should be always low at 0% duty cycle"


@cocotb.test()
async def test_pwm_100_percent(dut):
    """Test PWM with 100% duty cycle (always high)."""
    clock = Clock(dut.clk, 100, units="ns")  # 10 MHz
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Enable output on uo_out[0]
    await spi_write(dut, 0x00, 0x01)
    # Enable PWM mode on uo_out[0]
    await spi_write(dut, 0x02, 0x01)
    # Set duty cycle to 100% = 255
    await spi_write(dut, 0x04, 255)

    await ClockCycles(dut.clk, 5000)

    freq, duty = await measure_pwm(dut, 0, timeout_us=1000)

    dut._log.info(f"100% test - Frequency: {freq}, Duty Cycle: {duty}%")

    assert duty == 100.0 or freq is None, "Signal should be always high at 100% duty cycle"


@cocotb.test()
async def test_output_enable(dut):
    """Test that output is 0 when output enable is not set."""
    clock = Clock(dut.clk, 100, units="ns")  # 10 MHz
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Do NOT enable output, but set PWM and duty cycle
    await spi_write(dut, 0x02, 0x01)
    await spi_write(dut, 0x04, 128)

    await ClockCycles(dut.clk, 5000)

    # Output should be 0 since output enable is not set
    assert (int(dut.uo_out.value) & 1) == 0, "Output should be 0 when enable bit is not set"