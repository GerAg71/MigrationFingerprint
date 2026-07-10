      *> MAPTIVA stamped extract skeleton - card T650/01
      *> T650 Prod Mstr - T650/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T650-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  ACTION                       PIC X(1)         *> cols 9-9 Req
           05  REPORT-OPTION                PIC X(1)         *> cols 10-10 Req
           05  PRODUCT-ID                   PIC X(6)         *> cols 11-16 Opt
           05  FILLER-017-080               PIC X(64)        *> cols 17-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO ACTION
           MOVE <source-field> TO REPORT-OPTION
           MOVE <source-field> TO PRODUCT-ID
           MOVE SPACES TO FILLER-017-080
