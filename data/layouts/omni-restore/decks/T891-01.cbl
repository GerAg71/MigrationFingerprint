      *> MAPTIVA stamped extract skeleton - card T891/01
      *> T891 Ppt Source - T891/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T891-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  ACTION-FUNCTION              PIC X            *> cols 9-9 Req
           05  RPT-OPT-REPORT-OPTIONS       PIC X            *> cols 10-10 Req
           05  FILLER-011-080               PIC X(70)        *> cols 11-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO ACTION-FUNCTION
           MOVE <source-field> TO RPT-OPT-REPORT-OPTIONS
           MOVE SPACES TO FILLER-011-080
