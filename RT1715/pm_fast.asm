.386
.model flat
.code
public _rt_muldiv, _rt_dot14, _rt_span32, _rt_upload32
_rt_muldiv proc near
    mov eax,[esp+4]
    imul dword ptr [esp+8]
    idiv dword ptr [esp+12]
    ret
_rt_muldiv endp
; Full 64-bit dot product, same arithmetic shift as VISU/ACALC.ASM.
_rt_dot14 proc near
    push ebx
    push esi
    push edi
    mov esi,[esp+16]
    mov edi,[esp+20]
    mov eax,[esi]
    imul dword ptr [edi]
    mov ebx,eax
    mov ecx,edx
    mov eax,[esi+4]
    imul dword ptr [edi+4]
    add ebx,eax
    adc ecx,edx
    mov eax,[esi+8]
    imul dword ptr [edi+8]
    add ebx,eax
    adc ecx,edx
    shrd ebx,ecx,14
    mov eax,ebx
    pop edi
    pop esi
    pop ebx
    ret
_rt_dot14 endp
SPAN macro name,flat,bias
name:
    mov eax,ebx
    shr eax,6
    and eax,65535
if bias
    cmp eax,65535
    je name&_biased
    inc eax
name&_biased:
endif
    cmp ax,[esi]
    jb name&_skip
    mov [esi],ax
if flat
    mov [edi],cl
else
    mov eax,ecx
    sar eax,6
    mov [edi],al
endif
name&_skip:
    add ebx,[esp+36]
if flat EQ 0
    add ecx,[esp+44]
endif
    add esi,8
    inc edi
    dec ebp
    jnz name
    jmp span_done
endm
_rt_span32 proc near
    push ebx
    push esi
    push edi
    push ebp
    mov esi,[esp+20]
    mov edi,[esp+24]
    mov ebp,[esp+28]
    mov ebx,[esp+32]
    mov ecx,[esp+40]
    test ebp,ebp
    jz span_done
    cmp dword ptr [esp+44],0
    jne span_smooth
    sar ecx,6
    cmp dword ptr [esp+48],0
    jne flat_decal
    jmp flat_plain
span_smooth:
    cmp dword ptr [esp+48],0
    jne smooth_decal
    jmp smooth_plain
    SPAN flat_plain,1,0
    SPAN flat_decal,1,1
    SPAN smooth_plain,0,0
    SPAN smooth_decal,0,1
span_done:
    pop ebp
    pop edi
    pop esi
    pop ebx
    ret
_rt_span32 endp
_rt_upload32 proc near
    push esi
    push edi
    mov edi,[esp+12]
    mov esi,[esp+16]
    mov ecx,[esp+20]
    cld
    shr ecx,2
    rep movsd
    mov ecx,[esp+20]
    and ecx,3
    rep movsb
    pop edi
    pop esi
    ret
_rt_upload32 endp
; One entry per triangle: edge walking, scanline setup and inline pixel loops.
; Args offsets: vertices 0, depth 4, color 8, left 12, right 16,
; top 20, bottom 24, qx/qy/cx/cy 28..40, origins 44/48, decal 52, RAM 56, nonzero area 60.
; EBP locals: args -4, edge -8, plane -12, y -16, q -20, c -24,
; depth row -28, color row -32, dz -36, dc -40, spans -44, kernel -48.
; Setup deltas: dx1 -52, dy1 -56, dx2 -60, dy2 -64.
public _rt_triangle32
; Exact signed gradients: retain 64-bit numerator scaling and IDIV truncation.
TR_GRADIENT macro component,gradient
    mov eax,[edi+16+component]
    sub eax,[edi+component]
    imul eax,[ebp-64]
    mov ecx,[edi+32+component]
    sub ecx,[edi+component]
    imul ecx,[ebp-56]
    sub eax,ecx
    cdq
    shld edx,eax,6
    shl eax,6
    idiv dword ptr [esi+60]
    mov [esi+gradient],eax
    mov eax,[edi+32+component]
    sub eax,[edi+component]
    imul eax,[ebp-52]
    mov ecx,[edi+16+component]
    sub ecx,[edi+component]
    imul ecx,[ebp-60]
    sub eax,ecx
    cdq
    shld edx,eax,6
    shl eax,6
    idiv dword ptr [esi+60]
    mov [esi+gradient+4],eax
endm
TR_ORIGIN macro component,gradient,origin
    mov eax,[edi+component]
    shl eax,6
    mov ecx,[esi+gradient]
    imul ecx,[edi]
    sub eax,ecx
    mov ecx,[esi+20]
    sub ecx,[edi+4]
    imul ecx,[esi+gradient+4]
    add eax,ecx
    mov ecx,[esi+gradient]
    add ecx,[esi+gradient+4]
    mov edx,ecx
    shr edx,31
    add ecx,edx
    sar ecx,1
    add eax,ecx
    mov [esi+origin],eax
endm
_rt_triangle32 proc near
    push ebp
    mov ebp,esp
    sub esp,64
    push ebx
    push esi
    push edi
    mov esi,[ebp+8]
    mov [ebp-4],esi
    mov edi,[esi]
    mov eax,[edi+16]
    sub eax,[edi]
    mov [ebp-52],eax
    mov eax,[edi+20]
    sub eax,[edi+4]
    mov [ebp-56],eax
    mov eax,[edi+32]
    sub eax,[edi]
    mov [ebp-60],eax
    mov eax,[edi+36]
    sub eax,[edi+4]
    mov [ebp-64],eax
    TR_GRADIENT 8,28
    mov dword ptr [esi+36],0
    mov dword ptr [esi+40],0
    mov eax,[edi+12]
    cmp eax,[edi+28]
    jne tr_color_gradients
    cmp eax,[edi+44]
    je tr_origins
tr_color_gradients:
    TR_GRADIENT 12,36
tr_origins:
    TR_ORIGIN 8,28,44
    TR_ORIGIN 12,36,48
    mov dword ptr [ebp-44],0
    mov ebx,[esi+20]
    mov ecx,[esi+24]
    sub ecx,ebx
    jle tr_done
    mov edi,[esi+12]
    mov edx,[esi+16]
    lea edi,[edi+ebx*4]
    lea edx,[edx+ebx*4]
tr_init:
    mov dword ptr [edi],7fffffffh
    mov dword ptr [edx],80000001h
    add edi,4
    add edx,4
    dec ecx
    jnz tr_init
    mov dword ptr [ebp-8],0
tr_edge:
    mov esi,[ebp-4]
    mov edi,[esi]
    mov eax,[ebp-8]
    mov ecx,eax
    inc ecx
    cmp ecx,3
    jne tr_edge_index
    xor ecx,ecx
tr_edge_index:
    shl eax,4
    shl ecx,4
    lea esi,[edi+eax]
    add edi,ecx
    mov eax,[esi]
    mov ebx,[esi+4]
    mov edx,[edi]
    mov ecx,[edi+4]
    cmp ebx,ecx
    jle tr_edge_sorted
    xchg eax,edx
    xchg ebx,ecx
tr_edge_sorted:
    sub ecx,ebx
    jz tr_edge_next
    mov edi,eax
    sub edx,eax
    shl edx,16
    mov eax,edx
    cdq
    idiv ecx
    mov edx,eax
    shl edi,16
    mov esi,eax
    shr esi,31
    add eax,esi
    sar eax,1
    add eax,edi
    mov esi,[ebp-4]
    mov edi,[esi+16]
    mov esi,[esi+12]
    lea esi,[esi+ebx*4]
    lea edi,[edi+ebx*4]
tr_edge_walk:
    cmp eax,[esi]
    jge tr_left_ok
    mov [esi],eax
tr_left_ok:
    cmp eax,[edi]
    jle tr_right_ok
    mov [edi],eax
tr_right_ok:
    add eax,edx
    add esi,4
    add edi,4
    dec ecx
    jnz tr_edge_walk
tr_edge_next:
    inc dword ptr [ebp-8]
    cmp dword ptr [ebp-8],3
    jl tr_edge
    mov esi,[ebp-4]
    mov eax,[esi+28]
    shl eax,2
    mov [ebp-36],eax
    mov eax,[esi+36]
    shl eax,2
    mov [ebp-40],eax
    mov eax,offset tr_smooth_plain
    cmp dword ptr [esi+52],0
    je tr_choose_flat
    mov eax,offset tr_smooth_decal
tr_choose_flat:
    cmp dword ptr [ebp-40],0
    jne tr_chosen
    mov eax,offset tr_flat_plain
    cmp dword ptr [esi+52],0
    je tr_chosen
    mov eax,offset tr_flat_decal
tr_chosen:
    mov [ebp-48],eax
    mov dword ptr [ebp-12],0
tr_plane:
    mov esi,[ebp-4]
    mov ecx,[ebp-12]
    cmp dword ptr [esi+56],0
    jne tr_ram
    mov eax,100h
    shl eax,cl
    or eax,2
    mov dx,3c4h
    out dx,ax
    xor ecx,ecx
    jmp tr_address
tr_ram:
    imul ecx,16000
tr_address:
    add ecx,[esi+8]
    mov eax,[esi+20]
    mov [ebp-16],eax
    imul edx,eax,80
    add ecx,edx
    mov [ebp-32],ecx
    imul edx,eax,640
    add edx,[esi+4]
    mov [ebp-28],edx
    mov eax,[esi+44]
    mov [ebp-20],eax
    mov eax,[esi+48]
    mov [ebp-24],eax
tr_row:
    mov esi,[ebp-4]
    mov edx,[ebp-16]
    mov edi,[esi+12]
    mov eax,[edi+edx*4]
    add eax,32767
    sar eax,16
    mov edi,[esi+16]
    mov edx,[edi+edx*4]
    add edx,32767
    sar edx,16
    mov ecx,[ebp-12]
    sub ecx,eax
    and ecx,3
    add eax,ecx
    sub edx,eax
    jle tr_row_next
    add edx,3
    shr edx,2
    inc dword ptr [ebp-44]
    mov ebx,[esi+28]
    imul ebx,eax
    add ebx,[ebp-20]
    mov ecx,[esi+36]
    imul ecx,eax
    add ecx,[ebp-24]
    mov esi,[ebp-28]
    lea esi,[esi+eax*2]
    shr eax,2
    mov edi,[ebp-32]
    add edi,eax
    cmp dword ptr [ebp-40],0
    jne tr_pixels
    sar ecx,6
tr_pixels:
    jmp dword ptr [ebp-48]

TR_PIXELS macro name,flat,bias
name:
    mov eax,ebx
    shr eax,6
    and eax,65535
if bias
    cmp eax,65535
    je name&_biased
    inc eax
name&_biased:
endif
    cmp ax,[esi]
    jb name&_skip
    mov [esi],ax
if flat
    mov [edi],cl
else
    mov eax,ecx
    sar eax,6
    mov [edi],al
endif
name&_skip:
    add ebx,[ebp-36]
if flat EQ 0
    add ecx,[ebp-40]
endif
    add esi,8
    inc edi
    dec edx
    jnz name
    jmp tr_row_next
endm
    TR_PIXELS tr_flat_plain,1,0
    TR_PIXELS tr_flat_decal,1,1
    TR_PIXELS tr_smooth_plain,0,0
    TR_PIXELS tr_smooth_decal,0,1
tr_row_next:
    mov esi,[ebp-4]
    mov eax,[esi+32]
    add [ebp-20],eax
    mov eax,[esi+40]
    add [ebp-24],eax
    add dword ptr [ebp-28],640
    add dword ptr [ebp-32],80
    inc dword ptr [ebp-16]
    mov eax,[ebp-16]
    cmp eax,[esi+24]
    jl tr_row
    inc dword ptr [ebp-12]
    cmp dword ptr [ebp-12],4
    jl tr_plane
tr_done:
    mov eax,[ebp-44]
    pop edi
    pop esi
    pop ebx
    mov esp,ebp
    pop ebp
    ret
_rt_triangle32 endp

; Transform and project one object in one traversal. Keep camera-space vertices
; for clipping/backface tests and preserve signed 64-bit dot products.
extern _projmulx:dword, _projmuly:dword, _projaddx:dword, _projaddy:dword
extern _projclipx:dword, _projclipy:dword, _projclipz:dword
public _rt_transform_project
TDOT macro offset,dest,translation
    movsx eax,word ptr [ebx+offset]
    imul dword ptr [esi]
    mov ecx,eax
    mov [ebp-4],edx
    movsx eax,word ptr [ebx+offset+4]
    imul dword ptr [esi+4]
    add ecx,eax
    adc [ebp-4],edx
    movsx eax,word ptr [ebx+offset+8]
    imul dword ptr [esi+8]
    add ecx,eax
    adc [ebp-4],edx
    mov edx,[ebp-4]
    shrd ecx,edx,14
    add ecx,[ebx+translation]
    mov [edi+dest],ecx
endm
_rt_transform_project proc near
    push ebp
    mov ebp,esp
    sub esp,24
    push ebx
    push esi
    push edi
    mov eax,[ebp+8]
    mov [ebp-16],eax
    mov dword ptr [ebp-12],65535
    test eax,eax
    jz tp_done
    mov edi,[ebp+12]
    mov esi,[ebp+16]
    mov ebx,[ebp+20]
    mov eax,[ebp+24]
    mov [ebp-20],eax
    mov eax,[ebp+28]
    mov [ebp-24],eax
tp_loop:
    TDOT 0,0,36
    TDOT 12,4,40
    TDOT 24,8,44
    mov ax,[esi+12]
    mov [edi+12],ax
    mov ecx,[edi+8]
    mov dword ptr [ebp-8],0
    cmp ecx,512
    jge tp_near
    mov ecx,512
    or dword ptr [ebp-8],16
tp_near:
    cmp ecx,[_projclipz+4]
    jle tp_far
    or dword ptr [ebp-8],32
tp_far:
    mov eax,[edi+0]
    imul dword ptr [_projmulx]
    idiv ecx
    add eax,[_projaddx]
    mov edx,[ebp-20]
    mov [edx+0],eax
    mov edx,[ebp-24]
    mov [edx+0],eax
    cmp eax,[_projclipx]
    jge tp_xlow
    or dword ptr [ebp-8],4
tp_xlow:
    cmp eax,[_projclipx+4]
    jle tp_xhigh
    or dword ptr [ebp-8],8
tp_xhigh:
    mov eax,[edi+4]
    imul dword ptr [_projmuly]
    idiv ecx
    add eax,[_projaddy]
    mov edx,[ebp-20]
    mov [edx+4],eax
    mov edx,[ebp-24]
    mov [edx+4],eax
    cmp eax,[_projclipy]
    jge tp_ylow
    or dword ptr [ebp-8],1
tp_ylow:
    cmp eax,[_projclipy+4]
    jle tp_yhigh
    or dword ptr [ebp-8],2
tp_yhigh:
    mov eax,[ebp-8]
    mov edx,[ebp-20]
    mov [edx+8],eax
    and [ebp-12],eax
    test eax,16
    jnz tp_next
    mov eax,33553920
    xor edx,edx
    idiv ecx
    mov edx,[ebp-24]
    mov [edx+8],eax
tp_next:
    add edi,16
    add esi,16
    add dword ptr [ebp-20],12
    add dword ptr [ebp-24],16
    dec dword ptr [ebp-16]
    jnz tp_loop
tp_done:
    mov eax,[ebp-12]
    pop edi
    pop esi
    pop ebx
    mov esp,ebp
    pop ebp
    ret
_rt_transform_project endp
end
