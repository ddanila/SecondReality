; Same 237x31 UV walker as FOREST/ROUTINES.ASM. Seven glyph shades
; are filtered by the local water color through a 32x8 palette lookup.
bits 16
push ds
push bp
mov ds,ax
mov ax,0a000h
mov es,ax
mov fs,cx
mov gs,dx
mov dx,237*31
cell:
lodsw
or ax,ax
jz next
mov cx,ax
pixel:
lodsw
mov di,ax
mov al,[fs:bx]
or al,al
jz background
and ax,7
mov bp,ax
xor ax,ax
mov al,[gs:di]
shl ax,3
add bp,ax
mov al,[cs:blend+bp]
jmp store
background:
mov al,[gs:di]
store:
mov [es:di],al
loop pixel
next:
inc bx
dec dx
jnz cell
pop bp
pop ds
retf
blend: incbin "water-blend.bin"
