      *> MAPTIVA stamped extract skeleton - card T903/01
      *> T903 FC - T903/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T903-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-011               PIC X(6)         *> cols 6-11 Not Used
           05  OUTPUT-OPT-PRINT-ALL-FIELDS-VALUED-AND-UNVALUED PIC X            *> cols 12-12 Opt
           05  FILLER-013-080               PIC X(68)        *> cols 13-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-011
           MOVE <source-field> TO OUTPUT-OPT-PRINT-ALL-FIELDS-VALUED-AND-UNVALUED
           MOVE SPACES TO FILLER-013-080
