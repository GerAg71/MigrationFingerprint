      *> MAPTIVA stamped extract skeleton - card T650/02
      *> T650 Prod Mstr - T650/02
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T650-02-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  DE-NUMBER                    PIC 9(3)         *> cols 9-11 Req
           05  DE-VALUE                     PIC X(50)        *> cols 12-61 Req
           05  FILLER-062-080               PIC X(19)        *> cols 62-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO DE-NUMBER
           MOVE <source-field> TO DE-VALUE
           MOVE SPACES TO FILLER-062-080
