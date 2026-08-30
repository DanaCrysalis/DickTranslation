# Font engine

```
0008:00006AD7 668306EC2613        add  dword [26EC],0013                        
0008:00006ADD 66813EEC2612C90A00  cmp  dword [26EC],000AC912                    
0008:00006AE6 0F858A00            jnz  00006B74 ($+8a)        (down)            
0008:00006AEA 6657                push edi                                      
0008:00006AEC 6656                push esi                                      
0008:00006AEE 0FA0                push fs                                       
0008:00006AF0 06                  push es                                       
0008:00006AF1 6651                push ecx                                      
0008:00006AF3 6650                push eax                                      
0008:00006AF5 6633C9              xor  ecx,ecx                                  
0008:00006AF8 6633C0              xor  eax,eax                                  
0008:00006AFB B82000              mov  ax,0020                                  
0008:00006AFE 8EC0                mov  es,ax                                    
0008:00006B00 B83000              mov  ax,0030                                  
0008:00006B03 8EE0                mov  fs,ax                                    
0008:00006B05 66BE2F0C0500        mov  esi,00050C2F                             
0008:00006B0B 66BF91C60A00        mov  edi,000AC691                             
0008:00006B11 64678B0E            mov  cx,fs:[esi]            
0008:00006B15 81F9FFFF            cmp  cx,FFFF                                  
0008:00006B19 7422                je   00006B3D ($+22)        (no jmp)          
0008:00006B1B 90                  nop                                           
0008:00006B1C 90                  nop                                           
0008:00006B1D 6683C602            add  esi,0002                                 
0008:00006B21 F36467A4            repe fs:movsb                                 
0008:00006B25 64678B06            mov  ax,fs:[esi]            [illegal]         
0008:00006B29 3DFFFF              cmp  ax,FFFF                                  
0008:00006B2C 740F                je   00006B3D ($+f)         (no jmp)          
0008:00006B2E 90                  nop                                           
0008:00006B2F 90                  nop                                           
0008:00006B30 6603F8              add  edi,eax                                  
0008:00006B33 6683EF28            sub  edi,0028                                 
0008:00006B37 6683C602            add  esi,0002                                 
0008:00006B3B EBD4                jmp  short 00006B11 ($-2c)  (up)              
0008:00006B3D 6658                pop  eax                                      
0008:00006B3F 6659                pop  ecx                                      
0008:00006B41 07                  pop  es                                       
0008:00006B42 0FA1                pop  fs                                       
0008:00006B44 665E                pop  esi                                      
0008:00006B46 665F                pop  edi                                      
0008:00006B48 BDFFFF              mov  bp,FFFF                                  
0008:00006B4B 66C706EC26AE980A00  mov  dword [26EC],000A98AE                    
0008:00006B54 833EEA2601          cmp  word [26EA],0001       ds:[000026EA]=0061
0008:00006B59 7446                je   00006BA1 ($+46)        (no jmp)          
0008:00006B5B 90                  nop                                           
0008:00006B5C 90                  nop                                           
0008:00006B5D 803E36551C          cmp  byte [5536],1C         ds:[00005536]=0138
0008:00006B62 75F9                jne  00006B5D ($-7)         (up)              
0008:00006B64 803E36559C          cmp  byte [5536],9C         ds:[00005536]=0138
0008:00006B69 75F9                jne  00006B64 ($-7)         (up)              
0008:00006B6B E8A084              call FFFFF00E ($-7b60)                        
0008:00006B6E E8D984              call FFFFF04A ($-7b27)                        
0008:00006B71 E88800              call 00006BFC ($+88)                          
0008:00006B74 45                  inc  bp                                       
0008:00006B75 83FD0C              cmp  bp,000C                                  
0008:00006B78 7517                jne  00006B91 ($+17)        (down)            
0008:00006B7A 90                  nop                                           
0008:00006B7B 90                  nop                                           
0008:00006B7C BD0000              mov  bp,0000                                  
0008:00006B7F 66812EEC26E4000000  sub  dword [26EC],000000E4                    
0008:00006B88 668106EC26C0170000  add  dword [26EC],000017C0                    
0008:00006B91 668B0EC503          mov  ecx,[03C5]                               
0008:00006B96 67E2FD              loop 00006B96 ($-3)                           
0008:00006B99 FF0EEA26            dec  word [26EA]            ds:[000026EA]=0061
0008:00006B9D 0F855DFE            jnz  000069FE ($-1a3)       (up)              
0008:00006BA1 66C706EC26AE980A00  mov  dword [26EC],000A98AE                    
```

RELEVANT INSTRUCTIONS / RELEVANT VALUES:
```
0008:00006AD7 668306EC2613        add  dword [26EC],0013                        13
0008:00006ADD 66813EEC2612C90A00  cmp  dword [26EC],000AC912    				AC912
...
0008:00006B4B 66C706EC26AE980A00  mov  dword [26EC],000A98AE                    A98AE
...
0008:00006B75 83FD0C              cmp  bp,000C                                  0C
...
0008:00006B7F 66812EEC26E4000000  sub  dword [26EC],000000E4                    E4
0008:00006B88 668106EC26C0170000  add  dword [26EC],000017C0                    17C0
```

DIALOG BOX MEMORY OFFSETS:

|       |       |                |              |
|-------|-------|----------------|--------------|
| Row 1 | A98AE | = A98AE + 17C0 |              |
| Row 2 | AB06E | = AB06E + 17C0 |              |
| Row 3 | AC82E | = AC82E + E4   | E4 = 13 * 0C |
| End   | AC912 |                |              |






# Buy menu

code loading menu:

```
0008:0000A6A1 6656                push esi                                      
0008:0000A6A3 668D36942D          lea  esi,[2D94]                               
0008:0000A6A8 EB22                jmp  short 0000A6CC ($+22)  (down)            
0008:0000A6AA 90                  nop                                           
0008:0000A6AB 6656                push esi                                      
0008:0000A6AD 668D36A62D          lea  esi,[2DA6]                               
0008:0000A6B2 B90300              mov  cx,0003                                  
0008:0000A6B5 EB18                jmp  short 0000A6CF ($+18)  (down)            
0008:0000A6B7 90                  nop                                           
0008:0000A6B8 6656                push esi                                      
0008:0000A6BA 668D36862D          lea  esi,[2D86]                               
0008:0000A6BF EB0B                jmp  short 0000A6CC ($+b)   (down)            
0008:0000A6C1 90                  nop                                           
0008:0000A6C2 6656                push esi                                      
0008:0000A6C4 668D36782D          lea  esi,[2D78]                               
0008:0000A6C9 EB01                jmp  short 0000A6CC ($+1)   (down)            
0008:0000A6CB 90                  nop                                           
0008:0000A6CC B90200              mov  cx,0002                                  
0008:0000A6CF E873DA              call 00008145 ($-258d)                        
0008:0000A6D2 665E                pop  esi
```

MENU CODE OFFSETS<br/>
search for bytes: 6656668D36942D<br/>
found 84 results

MENU DEFINITION OFFSETS<br/>
search for bytes: D4970000457A<br/>
found 89 results

Match between ```lea esi,[2DXX]``` and the menu definition:<br/>


|      |                                   |           |                                                              |
|-------|------------------------------------|------------|---------------------------------------------------------------|
| 		    | 											                        | 					      | 		Solution to put Buy and Sell in the menu                    |
| 2D74	 | 		D4 97 00 00 						               | 					      |                                                               |
| 2D78	 | 		45 7A 01 00 64 04 05 92 			      | 	"OK"      |                                                               |
| 		    | 			  02 00 63 04 66 00 			         | 	"No  "			 | 		-> "No" (remove space glyph)                                |
| 2D86	 | 		45 7A 01 00 74 01 05 92 			      | 	"Y  "			  | 		2D84 (-2 bytes for glyph removed)                           |
| 		    | 			  02 00 63 04 66 00 			         | 	"No  "			 | 		-> "No" (remove space glyph)                                |
| 2D94	 | 		45 7A 02 00 86 04 CF 06 05 92 		 | 	"Rest"			 | 		2D90 (-4 bytes for glyphs removed)                          |
| 		    | 			  03 00 1F 04 E0 04 7C 01 		    | 	"Leave "  |                                                               |
| 2DA6	 | 		45 7A 01 00 88 03 05 92 			      | 	"Bu"			   | 		2DA2 (-4 bytes for glyphs removed), "Buy " (add <y > glyph) |
| 		    | 			  02 00 82 03 12 05 C5 A9 		    | 	"Back"    |                                                               |
| 		    | 			  01 00 8E 04 96 96 			         | 	"Se"			   | 		"Sell" (add <ll> glyph)                                     |
| 		    | 			  01 00 88 03 56 AE             |            |                                                               |
| 		    | 			  02 00 82 03 12 05 7F B2       |            |                                                               |
| 		    | 			  02 00 AD 04 7C 01 3F CA       |            |                                                               |
| 		    | 			  02 00 AA 03 7A 06 79 B2       |            |                                                               |
|       |                                    |            |                                                               |

