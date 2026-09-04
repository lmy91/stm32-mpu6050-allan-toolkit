/**
 * STM32F103C8T6 + MPU6050 logger for Allan-deviation analysis.
 * Wiring: VCC->3.3V, GND->GND, SCL->PB6, SDA->PB7, INT->PB0,
 *         USB-TTL RX->PA9.
 * Serial: 115200 8N1. Output is raw, uncalibrated CSV at 100 Hz.
 */
#include <stdbool.h>
#include <stdint.h>

#define REG32(a) (*(volatile uint32_t *)(a))
#define RCC_APB2ENR REG32(0x40021018u)
#define RCC_APB1ENR REG32(0x4002101Cu)
#define AFIO_EXTICR1 REG32(0x40010008u)
#define GPIOA_CRH   REG32(0x40010804u)
#define GPIOB_CRL   REG32(0x40010C00u)
#define GPIOB_BSRR  REG32(0x40010C10u)
#define GPIOB_BRR   REG32(0x40010C14u)
#define GPIOC_CRH   REG32(0x40011004u)
#define GPIOC_BSRR  REG32(0x40011010u)
#define GPIOC_BRR   REG32(0x40011014u)
#define USART1_SR   REG32(0x40013800u)
#define USART1_DR   REG32(0x40013804u)
#define USART1_BRR  REG32(0x40013808u)
#define USART1_CR1  REG32(0x4001380Cu)
#define I2C1_CR1    REG32(0x40005400u)
#define I2C1_CR2    REG32(0x40005404u)
#define I2C1_DR     REG32(0x40005410u)
#define I2C1_SR1    REG32(0x40005414u)
#define I2C1_SR2    REG32(0x40005418u)
#define I2C1_CCR    REG32(0x4000541Cu)
#define I2C1_TRISE  REG32(0x40005420u)
#define EXTI_IMR    REG32(0x40010400u)
#define EXTI_RTSR   REG32(0x40010408u)
#define EXTI_FTSR   REG32(0x4001040Cu)
#define EXTI_PR     REG32(0x40010414u)
#define NVIC_ISER0  REG32(0xE000E100u)
#define SYSTICK_CTRL REG32(0xE000E010u)
#define SYSTICK_LOAD REG32(0xE000E014u)
#define SYSTICK_VAL  REG32(0xE000E018u)

#define USART_TXE (1u << 7)
#define USART_TC  (1u << 6)
#define I2C_PE    (1u << 0)
#define I2C_START (1u << 8)
#define I2C_STOP  (1u << 9)
#define I2C_ACK   (1u << 10)
#define I2C_SWRST (1u << 15)
#define I2C_SB    (1u << 0)
#define I2C_ADDR  (1u << 1)
#define I2C_BTF   (1u << 2)
#define I2C_RXNE  (1u << 6)
#define I2C_TXE   (1u << 7)
#define I2C_BERR  (1u << 8)
#define I2C_ARLO  (1u << 9)
#define I2C_AF    (1u << 10)
#define I2C_OVR   (1u << 11)
#define I2C_BUSY  (1u << 1)
#define I2C_ERRORS (I2C_BERR | I2C_ARLO | I2C_AF | I2C_OVR)

#define MPU_SMPLRT_DIV   0x19u
#define MPU_CONFIG       0x1Au
#define MPU_GYRO_CONFIG  0x1Bu
#define MPU_ACCEL_CONFIG 0x1Cu
#define MPU_INT_PIN_CFG  0x37u
#define MPU_INT_ENABLE   0x38u
#define MPU_INT_STATUS   0x3Au
#define MPU_ACCEL_XOUT_H 0x3Bu
#define MPU_USER_CTRL    0x6Au
#define MPU_PWR_MGMT_1   0x6Bu
#define MPU_PWR_MGMT_2   0x6Cu
#define MPU_WHO_AM_I     0x75u
#define I2C_TIMEOUT_MS   5u
#define SAMPLE_RATE_HZ   100u

static volatile uint32_t g_ms;
static volatile uint32_t g_data_ready;
static volatile uint32_t g_data_ready_ms;
/* Volatile diagnostics can be inspected through ST-Link when no serial port
 * is connected: boot 0=start, 1=collecting, 0xE1=MPU not found. */
volatile uint32_t g_debug_boot_status;
volatile uint32_t g_debug_sample_count;
volatile uint32_t g_debug_last_dt_ms;
volatile uint32_t g_debug_i2c_errors;
volatile uint32_t g_debug_probe_mask;
volatile uint32_t g_debug_who_am_i;
volatile uint32_t g_debug_interrupt_count;
volatile uint32_t g_debug_interrupt_overruns;
volatile int16_t g_debug_last_raw[7];
static uint8_t g_mpu_addr = 0x68u;

/* Keep the reset-default 8 MHz HSI clock. */
void SystemInit(void) {}
void SysTick_Handler(void) { ++g_ms; }
void EXTI0_IRQHandler(void)
{
    if (EXTI_PR & 1u) {
        EXTI_PR = 1u; /* Write 1 to clear EXTI0 pending state. */
        g_data_ready_ms = g_ms;
        if (g_data_ready) ++g_debug_interrupt_overruns;
        g_data_ready = 1u;
        ++g_debug_interrupt_count;
    }
}
static uint32_t millis(void) { return g_ms; }

static void delay_ms(uint32_t delay)
{
    uint32_t start = millis();
    while ((uint32_t)(millis() - start) < delay) {}
}

static void board_init(void)
{
    SYSTICK_LOAD = 7999u;
    SYSTICK_VAL = 0u;
    SYSTICK_CTRL = 7u;

    RCC_APB2ENR |= (1u << 4);
    GPIOC_CRH = (GPIOC_CRH & ~(0xFu << 20)) | (0x2u << 20);
    GPIOC_BSRR = (1u << 13);
}

static void led_set(bool on)
{
    if (on) GPIOC_BRR = (1u << 13);
    else GPIOC_BSRR = (1u << 13);
}

static void uart_init(void)
{
    RCC_APB2ENR |= (1u << 0) | (1u << 2) | (1u << 14);
    /* PA9 AF push-pull 10 MHz; PA10 floating input. */
    GPIOA_CRH = (GPIOA_CRH & ~((0xFu << 4) | (0xFu << 8))) |
                (0x9u << 4) | (0x4u << 8);
    USART1_BRR = 0x45u; /* 115200 baud from 8 MHz PCLK2. */
    USART1_CR1 = (1u << 13) | (1u << 3) | (1u << 2);
}

static void mpu_interrupt_init(void)
{
    /* PB0 input with an internal pull-down. MPU6050 INT is active-high
     * push-pull; the pull-down prevents false 50 Hz edges if INT is unplugged. */
    RCC_APB2ENR |= (1u << 0) | (1u << 3); /* AFIO + GPIOB clocks. */
    GPIOB_CRL = (GPIOB_CRL & ~0xFu) | 0x8u;
    GPIOB_BRR = 1u; /* ODR=0 selects pull-down rather than pull-up. */

    /* Route EXTI0 to port B, trigger on rising edge, then enable IRQ 6. */
    AFIO_EXTICR1 = (AFIO_EXTICR1 & ~0xFu) | 0x1u;
    EXTI_IMR |= 1u;
    EXTI_RTSR |= 1u;
    EXTI_FTSR &= ~1u;
    EXTI_PR = 1u;
    NVIC_ISER0 = (1u << 6);
}

static void uart_putc(char c)
{
    while ((USART1_SR & USART_TXE) == 0u) {}
    USART1_DR = (uint8_t)c;
}

static void uart_puts(const char *s)
{
    while (*s) uart_putc(*s++);
}

static void uart_u32(uint32_t value)
{
    char digits[10];
    uint32_t count = 0u;
    do {
        digits[count++] = (char)('0' + value % 10u);
        value /= 10u;
    } while (value);
    while (count) uart_putc(digits[--count]);
}

static void uart_i16(int16_t value)
{
    int32_t wide = value;
    if (wide < 0) { uart_putc('-'); wide = -wide; }
    uart_u32((uint32_t)wide);
}

static void uart_flush(void)
{
    while ((USART1_SR & USART_TC) == 0u) {}
}

static void i2c_init(void)
{
    RCC_APB2ENR |= (1u << 0) | (1u << 3);
    RCC_APB1ENR |= (1u << 21);

    /* Recover a slave left mid-transfer when STM32 is reset during logging.
     * First use PB6/PB7 as open-drain GPIO, clock up to 9 remaining bits, and
     * synthesize STOP before handing the pins to I2C1. */
    GPIOB_CRL = (GPIOB_CRL & ~((0xFu << 24) | (0xFu << 28))) |
                (0x5u << 24) | (0x5u << 28);
    GPIOB_BSRR = (1u << 6) | (1u << 7);
    delay_ms(1u);
    for (uint32_t pulse = 0u; pulse < 9u; ++pulse) {
        GPIOB_BRR = (1u << 6);
        delay_ms(1u);
        GPIOB_BSRR = (1u << 6);
        delay_ms(1u);
    }
    GPIOB_BRR = (1u << 7);
    delay_ms(1u);
    GPIOB_BSRR = (1u << 6);
    delay_ms(1u);
    GPIOB_BSRR = (1u << 7);
    delay_ms(1u);

    /* PB6/PB7 AF open-drain 10 MHz; GY-521 supplies pull-ups. */
    GPIOB_CRL = (GPIOB_CRL & ~((0xFu << 24) | (0xFu << 28))) |
                (0xDu << 24) | (0xDu << 28);
    I2C1_CR1 = I2C_SWRST;
    I2C1_CR1 = 0u;
    I2C1_CR2 = 8u;
    I2C1_CCR = 40u;   /* 100 kHz standard mode. */
    I2C1_TRISE = 9u;
    I2C1_CR1 = I2C_PE;
}

static void i2c_abort(void)
{
    I2C1_CR1 |= I2C_STOP;
    I2C1_SR1 &= ~I2C_ERRORS;
    I2C1_CR1 |= I2C_SWRST;
    I2C1_CR1 = 0u;
    i2c_init();
}

static bool wait_sr1(uint32_t mask)
{
    uint32_t start = millis();
    while ((I2C1_SR1 & mask) == 0u) {
        if ((I2C1_SR1 & I2C_ERRORS) ||
            (uint32_t)(millis() - start) >= I2C_TIMEOUT_MS) return false;
    }
    return true;
}

static bool wait_idle(void)
{
    uint32_t start = millis();
    while (I2C1_SR2 & I2C_BUSY) {
        if ((uint32_t)(millis() - start) >= I2C_TIMEOUT_MS) return false;
    }
    return true;
}

static void clear_addr(void)
{
    volatile uint32_t dummy = I2C1_SR1;
    dummy = I2C1_SR2;
    (void)dummy;
}

static bool send_address(uint8_t address, bool read)
{
    I2C1_CR1 |= I2C_START;
    if (!wait_sr1(I2C_SB)) return false;
    I2C1_DR = ((uint32_t)address << 1) | (read ? 1u : 0u);
    return wait_sr1(I2C_ADDR);
}

static bool write_reg(uint8_t address, uint8_t reg, uint8_t value)
{
    if (!wait_idle() || !send_address(address, false)) goto fail;
    clear_addr();
    if (!wait_sr1(I2C_TXE)) goto fail;
    I2C1_DR = reg;
    if (!wait_sr1(I2C_TXE)) goto fail;
    I2C1_DR = value;
    if (!wait_sr1(I2C_BTF)) goto fail;
    I2C1_CR1 |= I2C_STOP;
    return true;
fail:
    i2c_abort();
    return false;
}

/* Supports one-byte reads and the 14-byte sensor burst read. */
static bool read_regs(uint8_t address, uint8_t reg, uint8_t *data, uint32_t count)
{
    if (count == 0u || count == 2u) return false;
    I2C1_CR1 |= I2C_ACK;
    if (!wait_idle() || !send_address(address, false)) goto fail;
    clear_addr();
    if (!wait_sr1(I2C_TXE)) goto fail;
    I2C1_DR = reg;
    if (!wait_sr1(I2C_BTF)) goto fail;
    /* A STOP between the register-pointer write and the read is accepted by
     * MPU6050 and avoids repeated-START edge cases seen on some Blue Pill and
     * GY-521 clone combinations. */
    I2C1_CR1 |= I2C_STOP;
    if (!wait_idle() || !send_address(address, true)) goto fail;

    if (count == 1u) {
        __asm volatile ("cpsid i" ::: "memory");
        I2C1_CR1 &= ~I2C_ACK;
        clear_addr();
        I2C1_CR1 |= I2C_STOP;
        __asm volatile ("cpsie i" ::: "memory");
        if (!wait_sr1(I2C_RXNE)) goto fail;
        data[0] = (uint8_t)I2C1_DR;
        return true;
    }

    clear_addr();
    while (count > 3u) {
        if (!wait_sr1(I2C_RXNE)) goto fail;
        *data++ = (uint8_t)I2C1_DR;
        --count;
    }
    if (!wait_sr1(I2C_BTF)) goto fail;
    I2C1_CR1 &= ~I2C_ACK;
    *data++ = (uint8_t)I2C1_DR;
    --count;
    I2C1_CR1 |= I2C_STOP;
    *data++ = (uint8_t)I2C1_DR;
    --count;
    if (!wait_sr1(I2C_RXNE)) goto fail;
    *data = (uint8_t)I2C1_DR;
    return true;
fail:
    i2c_abort();
    return false;
}

static bool mpu_read8(uint8_t reg, uint8_t *value)
{
    return read_regs(g_mpu_addr, reg, value, 1u);
}

static bool i2c_probe(uint8_t address)
{
    if (!wait_idle() || !send_address(address, false)) {
        i2c_abort();
        return false;
    }
    clear_addr();
    I2C1_CR1 |= I2C_STOP;
    delay_ms(1u);
    return true;
}

static bool mpu_find(void)
{
    uint8_t who = 0u;
    g_mpu_addr = 0x68u;
    if (i2c_probe(0x68u)) g_debug_probe_mask |= 1u;
    if (mpu_read8(MPU_WHO_AM_I, &who)) {
        g_debug_who_am_i = who;
        if (who == 0x68u) return true;
    }
    g_mpu_addr = 0x69u;
    if (i2c_probe(0x69u)) g_debug_probe_mask |= 2u;
    if (mpu_read8(MPU_WHO_AM_I, &who)) {
        g_debug_who_am_i = who;
        return who == 0x68u;
    }
    return false;
}

static bool mpu_init(void)
{
    if (!mpu_find()) return false;
    if (!write_reg(g_mpu_addr, MPU_PWR_MGMT_1, 0x80u)) return false;
    delay_ms(100u);
    return write_reg(g_mpu_addr, MPU_PWR_MGMT_1, 0x01u) &&
           write_reg(g_mpu_addr, MPU_PWR_MGMT_2, 0x00u) &&
           write_reg(g_mpu_addr, MPU_USER_CTRL, 0x00u) &&
           write_reg(g_mpu_addr, MPU_CONFIG, 0x03u) && /* 42/44 Hz DLPF */
           write_reg(g_mpu_addr, MPU_SMPLRT_DIV, 9u) && /* 100 Hz */
           write_reg(g_mpu_addr, MPU_GYRO_CONFIG, 0x00u) && /* +/-250 dps */
           write_reg(g_mpu_addr, MPU_ACCEL_CONFIG, 0x00u) && /* +/-2 g */
           /* Active-high push-pull, latched until INT_STATUS is read. A
            * latched level is much harder to miss than the short default
            * DATA_RDY pulse during long-duration logging. */
           write_reg(g_mpu_addr, MPU_INT_PIN_CFG, 0x20u) &&
           write_reg(g_mpu_addr, MPU_INT_ENABLE, 0x01u);
}

static int16_t i16be(uint8_t high, uint8_t low)
{
    return (int16_t)(((uint16_t)high << 8) | low);
}

static void print_header(void)
{
    uart_puts("# mpu6050_allan_logger_v2_int\r\n");
    uart_puts("# trigger=mpu6050_data_ready_int_pb0_rising\r\n");
    uart_puts("# sample_rate_hz=100\r\n");
    uart_puts("# accel_range_g=2\r\n");
    uart_puts("# accel_scale_lsb_per_g=16384\r\n");
    uart_puts("# gyro_range_dps=250\r\n");
    uart_puts("# gyro_scale_lsb_per_dps=131\r\n");
    uart_puts("# temperature_degC=temp_raw/340+36.53\r\n");
    uart_puts("# mpu_i2c_address=0x6");
    uart_putc(g_mpu_addr == 0x68u ? '8' : '9');
    uart_puts("\r\n");
    uart_puts("sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw\r\n");
}

static void print_sample(uint32_t sample, uint32_t now, uint32_t dt,
                         const uint8_t data[14])
{
    int16_t values[7] = {
        i16be(data[0], data[1]), i16be(data[2], data[3]),
        i16be(data[4], data[5]), i16be(data[6], data[7]),
        i16be(data[8], data[9]), i16be(data[10], data[11]),
        i16be(data[12], data[13])
    };
    uart_u32(sample); uart_putc(',');
    uart_u32(now); uart_putc(',');
    uart_u32(dt);
    for (uint32_t i = 0; i < 7u; ++i) {
        g_debug_last_raw[i] = values[i];
        uart_putc(',');
        uart_i16(values[i]);
    }
    uart_puts("\r\n");
}

int main(void)
{
    uint8_t status = 0u;
    uint8_t frame[14];
    uint32_t sample = 0u;
    uint32_t previous_ms;
    uint32_t errors = 0u;

    board_init();
    uart_init();
    i2c_init();
    mpu_interrupt_init();
    delay_ms(200u);
    uart_puts("# booting\r\n");

    if (!mpu_init()) {
        g_debug_boot_status = 0xE1u;
        uart_puts("# ERROR: MPU6050 not found; check 3.3V/GND/PB6/PB7\r\n");
        uart_flush();
        for (;;) led_set(((millis() / 150u) & 1u) != 0u);
    }

    delay_ms(100u);
    print_header();

    /* INT is configured as active-high and latched until INT_STATUS is read.
     * A DATA_RDY event normally occurs during the delay above, leaving PB0
     * high.  Clear that stale MPU latch before arming EXTI; otherwise clearing
     * only EXTI_PR loses the first edge and PB0 can remain high forever. */
    (void)mpu_read8(MPU_INT_STATUS, &status);
    __asm volatile ("cpsid i" ::: "memory");
    g_data_ready = 0u;
    EXTI_PR = 1u;
    previous_ms = millis();
    __asm volatile ("cpsie i" ::: "memory");
    g_debug_boot_status = 1u;

    for (;;) {
        /* The MPU6050 produces one DATA_RDY pulse per sample. EXTI0 records
         * its edge and timestamp; the relatively slow I2C/UART work stays
         * outside the interrupt handler. */
        if (!g_data_ready) continue;
        __asm volatile ("cpsid i" ::: "memory");
        uint32_t now = g_data_ready_ms;
        g_data_ready = 0u;
        __asm volatile ("cpsie i" ::: "memory");

        /* Acknowledge/clear MPU6050 DATA_RDY status so the next data-ready
         * event can generate a fresh INT pulse. This is not polling: EXTI0
         * has already told us that the event occurred. */
        if (!mpu_read8(MPU_INT_STATUS, &status)) {
            ++g_debug_i2c_errors;
            ++errors;
            continue;
        }
        if (!read_regs(g_mpu_addr, MPU_ACCEL_XOUT_H, frame, 14u)) {
            ++g_debug_i2c_errors;
            if (++errors >= 5u) {
                uart_puts("# ERROR: I2C retry\r\n");
                errors = 0u;
                delay_ms(20u);
                (void)mpu_init();
            }
            continue;
        }

        errors = 0u;
        uint32_t dt = now - previous_ms;
        print_sample(sample++, now, dt, frame);
        g_debug_sample_count = sample;
        g_debug_last_dt_ms = dt;
        previous_ms = now;
        led_set((sample % SAMPLE_RATE_HZ) < 4u);
    }
}
