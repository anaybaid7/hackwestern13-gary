#pragma once
#include "tensorflow/lite/interpreter_builder.h"
namespace tflite { namespace ops { namespace builtin {
class BuiltinOpResolver : public OpResolver {};
class BuiltinOpResolverWithXNNPACK : public BuiltinOpResolver {};
}}}
