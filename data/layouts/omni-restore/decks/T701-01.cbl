      *> MAPTIVA stamped extract skeleton - card T701/01
      *> T701 FC - T701/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T701-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  OPERATION                    PIC X(1)         *> cols 9-9 Req
           05  DENUM-DATA-ELEMENTS-DE       PIC X(3)         *> cols 10-12 Opt
           05  VAL-INTERNAL-DATA-ELEMENTS-VALUE PIC X(50)        *> cols 13-62 Opt
           05  FILLER-063-063               PIC X(1)         *> cols 63-63 Not Used
           05  CALC-OPTION                  PIC X(1)         *> cols 64-64 Opt
           05  REPORT-OPTION                PIC X(1)         *> cols 65-65 Opt
           05  FILLER-066-080               PIC X(15)        *> cols 66-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO OPERATION
           MOVE <source-field> TO DENUM-DATA-ELEMENTS-DE
           MOVE <source-field> TO VAL-INTERNAL-DATA-ELEMENTS-VALUE
           MOVE SPACES TO FILLER-063-063
           MOVE <source-field> TO CALC-OPTION
           MOVE <source-field> TO REPORT-OPTION
           MOVE SPACES TO FILLER-066-080
