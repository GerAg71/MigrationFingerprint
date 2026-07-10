      *> MAPTIVA stamped extract skeleton - card T613/01
      *> T613 Pln Maint - T613/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T613-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  DENUM-DATA-ELEMENTS-DE       PIC X(3)         *> cols 9-11 Opt
           05  VAL-INTERNAL-DATA-ELEMENTS-VALUE PIC X(40)        *> cols 12-51 Opt
           05  RPT-OPT                      PIC X            *> cols 52-52 Opt
           05  OVERRIDE-CALC-IND            PIC X            *> cols 53-53 Opt
           05  FILLER-054-080               PIC X(27)        *> cols 54-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO DENUM-DATA-ELEMENTS-DE
           MOVE <source-field> TO VAL-INTERNAL-DATA-ELEMENTS-VALUE
           MOVE <source-field> TO RPT-OPT
           MOVE <source-field> TO OVERRIDE-CALC-IND
           MOVE SPACES TO FILLER-054-080
