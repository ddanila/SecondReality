; Experimental 800x70 texture, per-screen-pixel half-texel UV coordinates.
; Original caller supplies AX:SI map, DX background. Cue code stays intact.
bits 16
org 0
jmp near render
advance_entry: jmp advance
scroll: dw 0
render:
push ds
push bp
push bx
mov ds,ax
mov ax,0a000h
mov es,ax
mov gs,dx
mov cx,[si]
add si,2
pixel:
lodsw
mov di,ax
lodsw
add ax,[cs:scroll]
sub ax,316
js background
cmp ax,640
jb source
and ax,127
add ax,640
source:
mov bp,ax
lodsw
add bp,ax
mov al,[cs:texture+bp]
or al,al
jnz store
jmp restore
background:
add si,2
restore:
mov al,[gs:di]
store:
mov [es:di],al
loop pixel
pop bx
pop bp
pop ds
retf
advance:
; Keep the original source pointer inside its old buffer, for its unused copy.
cmp word [ds:528eh],383
jb increment
mov word [ds:528eh],319
increment:
inc word [ds:528eh]
add word [cs:scroll],2
cmp word [cs:scroll],1152
jb done
sub word [cs:scroll],128
done:
retf
texture: incbin "tape-800x70.bin"
