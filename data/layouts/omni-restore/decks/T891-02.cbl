      *> MAPTIVA stamped extract skeleton - card T891/02
      *> T891 Ppt Source - T891/02
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T891-02-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  DENUM-DATA-ELEMENTS-DE       PIC X(3)         *> cols 9-11 Req
           05  DEVAL-DATA-ELEMENTS-VALUE    PIC X(50)        *> cols 12-61 Req
           05  FILLER-062-080               PIC X(19)        *> cols 62-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO DENUM-DATA-ELEMENTS-DE
           MOVE <source-field> TO DEVAL-DATA-ELEMENTS-VALUE
           MOVE SPACES TO FILLER-062-080
