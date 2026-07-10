      *> MAPTIVA stamped extract skeleton - card T613/02-30
      *> T613 Pln Maint - T613/02-30
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T613-02-30-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  DENUM-DATA-ELEMENTS-DE       PIC X(3)         *> cols 9-11 Opt
           05  VAL-INTERNAL-DATA-ELEMENTS-VALUE PIC X(40)        *> cols 12-51 Opt
           05  FILLER-052-052               PIC X(1)         *> cols 52-52 Not Used
           05  FILLER-053-080               PIC X(28)        *> cols 53-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO DENUM-DATA-ELEMENTS-DE
           MOVE <source-field> TO VAL-INTERNAL-DATA-ELEMENTS-VALUE
           MOVE SPACES TO FILLER-052-052
           MOVE SPACES TO FILLER-053-080
