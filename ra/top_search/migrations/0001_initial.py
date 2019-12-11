# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ra', '0001_initial'),
        ('cash', '0001_initial'),
        ('store', '0001_initial'),
        ('payment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TopSearchModel',
            fields=[
                ('id', models.PositiveIntegerField(serialize=False, primary_key=True)),
                ('slug', models.CharField(max_length=255)),
                ('title', models.TextField()),
                ('blob_text', models.TextField(null=True)),
                ('identifier', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
                'db_table': 'ra_topsearch',
                'managed': False,
            },
        ),
        migrations.RunSQL("""
        create  VIEW ra_topsearch as
            SELECT ID, SLUG , title ,  '' as blob_text, 'client' as identifier
            from store_client
            UNION ALL
            SELECT ID, SLUG , title ,  '', 'supplier'
            from store_supplier
            UNION ALL
            SELECT ID, SLUG , title ,  '', 'agent'
            from store_agent
            UNION ALL
            SELECT ID, SLUG , title ,  '', 'product'
            from store_product
            UNION ALL
            SELECT ID, SLUG , title ,  '', 'productcategory'
            from store_productcategory
            UNION ALL
            SELECT ID, SLUG , title ,  '', 'store'
            from store_store
            UNION ALL
            SELECT ID, SLUG , title ,  '', 'tax'
            from store_tax
            UNION ALL
            SELECT ID, SLUG , title ,  '', 'measureunit'
            from store_measureunit
            UNION ALL
            SELECT ID, SLUG , slug  ,  '', doc_type
            from store_itemmovement
            UNION ALL
            SELECT ID, SLUG , slug ,  '', doc_type
            from store_transfer

            UNION ALL
            SELECT ID, SLUG , title ,  '', 'treasury'
            from cash_treasury

            UNION ALL
            SELECT ID, SLUG , title ,  '', 'expense'
            from cash_expense

            UNION ALL
            SELECT ID, SLUG , title ,  '', 'liability'
            from cash_liability

            UNION ALL
            SELECT ID, SLUG , title ,  '', 'operation'
            from cash_operation

            UNION ALL
            SELECT ID, SLUG , title ,  '', 'income'
            from cash_income

            UNION ALL
            SELECT ID, SLUG , slug ,  '', doc_type
            from cash_treasurytransfer

            UNION ALL
            SELECT ID, SLUG , slug ,  '', doc_type
            from cash_expensemovement
            UNION ALL
            SELECT ID, SLUG , slug ,  '', doc_type
            from cash_liabilitymovement
            UNION ALL
            SELECT ID, SLUG , slug ,  '', doc_type
            from cash_incomemovement
            UNION ALL
            SELECT ID, SLUG , slug ,  '', doc_type
            from payment_paymentmovement

        """),

        migrations.RunSQL("""
            create MATERIALIZED VIEW ra_topsearch_materialized as
            select * from ra_topsearch ;
           create INDEX search_title on ra_topsearch_materialized(title);
            create INDEX search_slug on ra_topsearch_materialized(slug);
        """)
    ]
