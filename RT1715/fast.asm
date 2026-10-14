; Real-mode 386 kernels. All entries are FAR, stack cdecl; preserve the
; caller's registers and segment registers except documented return values.
; BP+6 is the first argument after PUSH BP and a four-byte far return address.
.model large
.386
.code
public _rt_muldiv, _rt_span386, _rt_clear386, _rt_copy386
public _rt_edges386

_rt_muldiv proc far
    push bp
    mov bp,sp
    mov eax,dword ptr [bp+6]
    imul dword ptr [bp+10]
    idiv dword ptr [bp+14]
    mov edx,eax
    shr edx,16
    pop bp
    retf
_rt_muldiv endp

_rt_clear386 proc far
    push bp
    mov bp,sp
    push eax
    push cx
    push di
    push es
    les di,dword ptr [bp+6]
    mov cx,[bp+10]
    shr cx,2
    xor eax,eax
    cld
    rep stosd
    mov cx,[bp+10]
    and cx,3
    rep stosb
    pop es
    pop di
    pop cx
    pop eax
    pop bp
    retf
_rt_clear386 endp

_rt_copy386 proc far
    push bp
    mov bp,sp
    push cx
    push si
    push di
    push ds
    push es
    les di,dword ptr [bp+6]
    lds si,dword ptr [bp+10]
    mov cx,[bp+14]
    shr cx,2
    cld
    rep movsd
    mov cx,[bp+14]
    and cx,3
    rep movsb
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop bp
    retf
_rt_copy386 endp

; Initialize the active scanline bounds and walk all three triangle edges.
; Locals: edge index -2, left base -4, right base -6, vertex base -8.
; This batches the short loops under one C/assembly call per triangle.
_rt_edges386 proc far
    push bp
    mov bp,sp
    sub sp,8
    pushad
    push ds
    push es
    push fs
    les di,dword ptr [bp+10]
    lfs si,dword ptr [bp+14]
    mov [bp-4],di
    mov [bp-6],si
    mov bx,[bp+18]
    mov cx,[bp+20]
    sub cx,bx
    jle edges_done
    shl bx,2
    add di,bx
    add si,bx
    mov eax,7fffffffh
    mov edx,80000001h
edges_init:
    mov es:[di],eax
    mov fs:[si],edx
    add di,4
    add si,4
    dec cx
    jnz edges_init
    lds si,dword ptr [bp+6]
    mov [bp-8],si
    mov word ptr [bp-2],0
edges_next:
    mov si,[bp-2]
    mov di,si
    inc di
    cmp di,3
    jne edges_index
    xor di,di
edges_index:
    shl si,4
    shl di,4
    add si,[bp-8]
    add di,[bp-8]
    mov eax,[si]
    mov ebx,[si+4]
    mov edx,[di]
    mov ecx,[di+4]
    cmp ebx,ecx
    jle edges_ordered
    xchg eax,edx
    xchg ebx,ecx
edges_ordered:
    sub ecx,ebx
    jz edges_advance
    mov esi,eax
    sub edx,eax
    shl edx,16
    mov eax,edx
    cdq
    idiv ecx
    mov edx,eax
    shl esi,16
    ; C division by two truncates toward zero, including negative slopes.
    mov edi,eax
    shr edi,31
    add eax,edi
    sar eax,1
    add eax,esi
    shl bx,2
    mov di,[bp-4]
    mov si,[bp-6]
    add di,bx
    add si,bx
edges_walk:
    cmp eax,es:[di]
    jge edges_left_ok
    mov es:[di],eax
edges_left_ok:
    cmp eax,fs:[si]
    jle edges_right_ok
    mov fs:[si],eax
edges_right_ok:
    add eax,edx
    add di,4
    add si,4
    dec cx
    jnz edges_walk
edges_advance:
    inc word ptr [bp-2]
    cmp word ptr [bp-2],3
    jne edges_next
edges_done:
    pop fs
    pop es
    pop ds
    popad
    add sp,8
    pop bp
    retf
_rt_edges386 endp

; One already-selected VGA plane. Depth advances by four pixels (8 bytes),
; while VGA advances one byte. q and shade use six fractional bits.
; Keep interpolation in 32-bit registers; only the temporary depth test
; borrows EAX. The decal loop saturates its one-unit bias at 65535.
SPAN_LOOP macro label_name,bias
local rejected,next_pixel
label_name:
    push eax
    sar eax,6
    if bias
        cmp ax,65535
        je next_pixel
        inc ax
next_pixel:
    endif
    cmp ax,fs:[si]
    jb rejected
    mov fs:[si],ax
    mov eax,ecx
    sar eax,6
    mov es:[di],al
rejected:
    pop eax
    add eax,ebx
    add ecx,edx
    add si,8
    inc di
    dec bp
    jnz label_name
endm

_rt_span386 proc far
    push bp
    mov bp,sp
    pushad
    push ds
    push es
    push fs
    lds si,dword ptr [bp+6]
    mov ax,[si]
    mov fs,ax
    mov ax,[si+4]
    mov es,ax
    mov di,[si+6]
    mov bp,[si+8]
    test bp,bp
    jz span_done
    mov eax,[si+12]
    mov ebx,[si+16]
    mov ecx,[si+20]
    mov edx,[si+24]
    cmp word ptr [si+10],0
    mov si,[si+2]
    jnz span_decal
    SPAN_LOOP span_plain,0
    jmp span_done
span_decal:
    SPAN_LOOP span_biased,1
span_done:
    pop fs
    pop es
    pop ds
    popad
    pop bp
    retf
_rt_span386 endp
end
