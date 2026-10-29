#version 450
layout(location = 0) in vec4 a_position;
/* xsdk's GLSL vertex-input convention maps location 2 to TEXCOORD0.
 * Location 1 is COLOR0, so using it for UVs makes
 * xsdk_shader_set_vertex_layout() reject the layout on real hardware. */
layout(location = 2) in vec2 a_uv;
layout(location = 0) out vec2 v_uv;

void main()
{
    gl_Position = a_position;
    v_uv = a_uv;
}
