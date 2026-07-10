      *> MAPTIVA stamped extract skeleton - card T813/02-T813/99
      *> T813 Ppt Hdr Maint - T813/02 – 813/99
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T813-02-T813-99-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  DENUM-OLD-DATA-ELEMENTS-DE   PIC X(3)         *> cols 9-11 Opt
           05  FILLER-012-017               PIC X(6)         *> cols 12-17 Not Used
           05  CALC-OPT-CALC-OPTIONS        PIC X            *> cols 18-18 Opt
           05  VAL-INTERNAL-DATA-ELEMENTS-VALUE PIC X(50)        *> cols 19-68 Opt
           05  DENUM-DATA-ELEMENTS-DE       PIC X(3)         *> cols 69-71 Opt
           05  FILLER-072-080               PIC X(9)         *> cols 72-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO DENUM-OLD-DATA-ELEMENTS-DE
           MOVE SPACES TO FILLER-012-017
           MOVE <source-field> TO CALC-OPT-CALC-OPTIONS
           MOVE <source-field> TO VAL-INTERNAL-DATA-ELEMENTS-VALUE
           MOVE <source-field> TO DENUM-DATA-ELEMENTS-DE
           MOVE SPACES TO FILLER-072-080
