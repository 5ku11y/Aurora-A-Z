#version 450
layout(location = 0) in vec4 a_position;
layout(location = 1) in vec2 a_uv;
layout(location = 0) out vec2 v_uv;

void main()
{
    gl_Position = a_position;
    v_uv = a_uv;
}
