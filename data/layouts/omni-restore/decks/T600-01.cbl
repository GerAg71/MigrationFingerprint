      *> MAPTIVA stamped extract skeleton - card T600/01
      *> T600 Add a Plan - T600/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T600-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE-KEY-DATA-SEQ-NUM    PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  PLAN-TYPE-PL089              PIC X            *> cols 9-9 Opt
           05  PLAN-YEAR-END-DATE-PL803     PIC X(4)         *> cols 10-13 Req
           05  COMPANY-IRS-NUM-PL882-NOTE-FIELD-MAY-BE-POPULATED-WITH-ZEROES-I-E-000000000 PIC 9(9)         *> cols 14-22 Req
           05  ADMINISTRATOR-ID-NUM         PIC X(6)         *> cols 23-28 Opt
           05  ADMINISTRATOR-NAME           PIC X(30)        *> cols 29-58 Opt
           05  NEW-PLAN-ID                  PIC X(6)         *> cols 59-64 Req
           05  FILLER-065-080               PIC X(16)        *> cols 65-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE-KEY-DATA-SEQ-NUM
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO PLAN-TYPE-PL089
           MOVE <source-field> TO PLAN-YEAR-END-DATE-PL803
           MOVE <source-field> TO COMPANY-IRS-NUM-PL882-NOTE-FIELD-MAY-BE-POPULATED-WITH-ZEROES-I-E-000000000
           MOVE <source-field> TO ADMINISTRATOR-ID-NUM
           MOVE <source-field> TO ADMINISTRATOR-NAME
           MOVE <source-field> TO NEW-PLAN-ID
           MOVE SPACES TO FILLER-065-080
