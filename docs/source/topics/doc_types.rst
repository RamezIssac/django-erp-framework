

Document types
===============

What are document types ?
-------------------------

To answer this question we would need to go over a little of accounting and explore the idea of double entry bookkeeping.
Double entry bookkeeping is a system of accounting in which every transaction has a corresponding opposite transaction.
For example, if you buy a car for $10,000, you would record a $10,000 debit to the asset account for your car and a $10,000 credit to the cash account.
Document types are the way to define the type of transaction that is being recorded.

This allows the reporting engine to know how to handle transactions / entries and how to compute it.

Example:

        - A sale is a transaction that will increase the revenue account and decrease the inventory account.
        - A purchase is a transaction that will increase the inventory account and decrease the cash account.
        - A payment is a transaction that will decrease the cash account and decrease the accounts payable account.

The reporting engine will use the document type to know how to compute the transaction.
ie: shall it a plus or a minus, or in accounting terms shall it be a debit or a credit.

The ``ReportView`` have attributes that lets you control the document types .

You can see it in action in the demo application.
In order to compute profitability , the system needed to distinguish between the expenses and the sales
Code on github : https://github.com/RamezIssac/my-shop/blob/main/general_reports/reports.py


.. code-block:: python


        class MyReportView(ReportView):

            doc_type_field_name = "doc_type"
            doc_type_plus_list = ['sales', 'other-revenue']
            doc_type_minus_list = ['expense', 'purchase', 'other-expense']


Here the report will look at the report_model and check the doc_type_field_name (doc_type in the example above)
All the transactions that have a doc_type in the doc_type_plus_list will be added to the plus side of the report calculation
All the transactions that have a doc_type in the doc_type_minus_list will be added to the minus side of the report calculation

This way the report will be able to compute the profit and loss of the company (or any other report that you want to create)


