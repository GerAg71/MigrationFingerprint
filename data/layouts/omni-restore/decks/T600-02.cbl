      *> MAPTIVA stamped extract skeleton - card T600/02
      *> T600 Add a Plan - T600/02
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T600-02-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE-KEY-DATA-SEQ-NUM    PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  PLAN-NAME-LINE-1             PIC X(32)        *> cols 9-40 Opt
           05  FILLER-041-080               PIC X(40)        *> cols 41-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE-KEY-DATA-SEQ-NUM
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO PLAN-NAME-LINE-1
           MOVE SPACES TO FILLER-041-080
