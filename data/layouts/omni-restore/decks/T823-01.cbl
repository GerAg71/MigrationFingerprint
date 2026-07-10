      *> MAPTIVA stamped extract skeleton - card T823/01
      *> T823 PF - T823/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T823-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  DENUM-PF-DATA-ELEMENT-NUMBER PIC X(3)         *> cols 9-11 Req
           05  DEVAL-PF-DATA-ELEMENT-VALUE  PIC X(32)        *> cols 12-43 Req
           05  FILLER-044-053               PIC X(10)        *> cols 44-53 Not Used
           05  RPT-OPT-REPORT-OPTIONS       PIC X            *> cols 54-54 Opt
           05  UPDATE-SYNC-UPDATE-FUND-CONTROL-RECORDS PIC X            *> cols 55-55 Opt
           05  AUTO-CREATE-OPT-AUTO-CREATE-PF-RECORD PIC X            *> cols 56-56 Opt
           05  FILLER-057-058               PIC X(2)         *> cols 57-58 Not Used
           05  CALC-OPT-CALC-OPTIONS        PIC X            *> cols 59-59 Opt
           05  FILLER-060-080               PIC X(21)        *> cols 60-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO DENUM-PF-DATA-ELEMENT-NUMBER
           MOVE <source-field> TO DEVAL-PF-DATA-ELEMENT-VALUE
           MOVE SPACES TO FILLER-044-053
           MOVE <source-field> TO RPT-OPT-REPORT-OPTIONS
           MOVE <source-field> TO UPDATE-SYNC-UPDATE-FUND-CONTROL-RECORDS
           MOVE <source-field> TO AUTO-CREATE-OPT-AUTO-CREATE-PF-RECORD
           MOVE SPACES TO FILLER-057-058
           MOVE <source-field> TO CALC-OPT-CALC-OPTIONS
           MOVE SPACES TO FILLER-060-080
