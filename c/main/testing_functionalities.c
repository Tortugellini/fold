/*
Remember for later use.

xTaskCreatePinnedToCore(
    blinkLED,
    "Task 1",
    1024,
    NULL,
    1,
    &task_1,
    1
);

*/

#include <stdio.h>
#include <string.h>
#include "FreeRTOS.h"
#include "driver/ledc.h"
#include "freertos/task.h"

#define ON_BOARD_LED_GPIO_NUM  (2)  // The channel chosen points to the on-board LED.
#define LEDC_TEST_CH_NUM       (1)
#define LEDC_TEST_DUTY         (4096)
#define LEDC_TEST_FADE_TIME    (3000)

// static TaskHandle_t task_1 = NULL;
// static TaskHandle_t task_2 = NULL;

void app_main() {
    int ch;

    ledc_timer_config_t led_timer = {
        .duty_resolution = LEDC_TIMER_8_BIT,
        .freq_hz = 5000,
        .speed_mode = LEDC_HIGH_SPEED_MODE,
        .timer_num = LEDC_TIMER_0
    };

    ledc_timer_config(& led_timer);

    // Configuring the channel used for PWM.
    ledc_channel_config_t ledc_channel[LEDC_TEST_CH_NUM] = {
        {
            .channel    = LEDC_CHANNEL_0,
            .duty       = 25,
            .gpio_num   = ON_BOARD_LED_GPIO_NUM,
            .speed_mode = LEDC_HIGH_SPEED_MODE,
            .hpoint     = 0,
            .timer_sel  = LEDC_TIMER_0
        }
    };

    // Set LED Controller with previously prepared configuration
    for (ch = 0; ch < LEDC_TEST_CH_NUM; ch++) {
        ledc_channel_config(&ledc_channel[ch]);
    }

    ledc_fade_func_install(0);

    while (1) {
        // printf("Fading out the LED ");
        // for (ch =0; ch < LEDC_TEST_CH_NUM; ch++) {
        //     ledc_set_fade_with_time(
        //         ledc_channel[ch].speed_mode,
        //         ledc_channel[ch].channel,
        //         LEDC_TEST_DUTY,
        //         LEDC_TEST_FADE_TIME
        //     );
        //     ledc_fade_start(
        //         ledc_channel[ch].speed_mode,
        //         ledc_channel[ch].channel,
        //         LEDC_FADE_WAIT_DONE
        //     );
        // }

        // vTaskDelay(LEDC_TEST_FADE_TIME / portTICK_PERIOD_MS);

        printf("Blinking the LED ");
        for (ch = 0; ch < LEDC_TEST_CH_NUM; ch++) {
            ledc_set_duty(
                ledc_channel[ch].speed_mode,
                ledc_channel[ch].channel,
                25
            );
            ledc_update_duty(
                ledc_channel[ch].speed_mode,
                ledc_channel[ch].channel
            );
        }
    }
}
