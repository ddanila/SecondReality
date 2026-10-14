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
end
