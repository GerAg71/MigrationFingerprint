      *> MAPTIVA stamped extract skeleton - card T600/08
      *> T600 Add a Plan - T600/08
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T600-08-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE-KEY-DATA-SEQ-NUM    PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  TRUSTEE-NAME                 PIC X(30)        *> cols 9-38 Opt
           05  FILLER-039-080               PIC X(42)        *> cols 39-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE-KEY-DATA-SEQ-NUM
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO TRUSTEE-NAME
           MOVE SPACES TO FILLER-039-080
