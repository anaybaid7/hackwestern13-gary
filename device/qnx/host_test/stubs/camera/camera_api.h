// Stub of QNX <camera/camera_api.h> for compile checks on Linux only.
#pragma once
#include <errno.h>
#include <stdint.h>
#ifndef EOK
#define EOK 0
#endif
typedef int32_t camera_handle_t;
#define CAMERA_HANDLE_INVALID (-1)
typedef enum { CAMERA_UNIT_NONE = 0, CAMERA_UNIT_1, CAMERA_UNIT_2, CAMERA_UNIT_3, CAMERA_UNIT_4, CAMERA_UNIT_5 } camera_unit_t;
typedef struct camera_buffer camera_buffer_t;
