      *> MAPTIVA stamped extract skeleton - card T801/01
      *> T801 Ppt Create - T801/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T801-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  FUNCTION-FUNCTION            PIC X(15)        *> cols 9-23 Req
           05  FILLER-024-025               PIC X(2)         *> cols 24-25 Not Used
           05  LOCATION                     PIC X(4)         *> cols 26-29 Opt
           05  OVERRIDE-CALC-IND-VALIDATE-OVERRIDE PIC X            *> cols 30-30 Opt
           05  FILLER-031-080               PIC X(50)        *> cols 31-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO FUNCTION-FUNCTION
           MOVE SPACES TO FILLER-024-025
           MOVE <source-field> TO LOCATION
           MOVE <source-field> TO OVERRIDE-CALC-IND-VALIDATE-OVERRIDE
           MOVE SPACES TO FILLER-031-080
