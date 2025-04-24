from .factories import CustomerFactory, CustomerPhoneFactory, PremiumCustomerFactory, SubscriptionFactory


class CreateCustomersMixin(object):
    def create_customers(self, **kwargs):
        """
        Helper function to create customers with various different subscription statuses.
        """
        self.customers = []
        # 0: seen, but that's all
        self.customers.append(CustomerFactory(unregistered=True, **kwargs))

        # 1: requested stop without registering
        self.customers.append(CustomerFactory(unregistered=True, has_requested_stop=True, **kwargs))

        # 2: standard active customer
        self.customers.append(CustomerFactory(**kwargs))

        # 3: requested stop
        self.customers.append(CustomerFactory(has_requested_stop=True, **kwargs))

        # 4: digifarm customer
        customer4 = CustomerFactory(**kwargs)
        customer4.digifarm_farmer_id = "4929951568174104"
        phone2 = CustomerPhoneFactory(number='+4929951568174104', is_main=False, customer=customer4)
        assert (customer4.phones.count() == 2)
        customer4.save()
        self.customers.append(customer4)

        # 5: stopped digifarm customer
        customer5 = CustomerFactory(has_requested_stop=True, **kwargs)
        customer5.digifarm_farmer_id = "4929951568174105"
        phone2 = CustomerPhoneFactory(number='+4929951568174105', is_main=False, customer=customer5)
        customer5.save()
        self.customers.append(customer5)

        # 6: digifarm customer with no africas_talking_number
        customer6 = CustomerFactory(**kwargs, has_no_phones=True)
        customer6.digifarm_farmer_id = "4929951568174106"
        assert(customer6.phones.count() == 0)
        phone = CustomerPhoneFactory(number='+4929951568174106', is_main=False, customer=customer6)
        customer6.save()
        self.customers.append(customer6)

        # 7: An "invalid" digifarm customer with normal number in the phone field
        customer7 = CustomerFactory(**kwargs)
        assert (customer7.phones.count() == 1)
        customer7.digifarm_farmer_id = "4929951568174107"
        customer7.save()
        self.customers.append(customer7)

        # 8: An "invalid" africas_talking customer with digifarm phone number in the phone fields
        # customer8 = CustomerFactory(**kwargs, has_no_phones=True)
        # customer8.digifarm_farmer_id = None
        # assert (customer8.phones.count() == 0)
        # phone = CustomerPhoneFactory(number='+4929951568174108', is_main=True, customer=customer8)
        # customer8.save()
        # self.customers.append(customer8)


class CreateCustomersWithPremiumMixin(CreateCustomersMixin):
    def create_customers(self, **kwargs):
        super().create_customers(**kwargs)

        # 9: Customer with premium subscription
        self.customer9 = PremiumCustomerFactory(
            subscriptions=(SubscriptionFactory(),)
        )
