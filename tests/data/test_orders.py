"""Testes das consultas de pedidos e clientes."""


def test_get_order(repos):
    order = repos.orders.get("O1")

    assert order.customer_id == "C1"
    assert order.status == "delivered"
    assert order.total_brl == 1999.00


def test_get_order_unknown(repos):
    assert repos.orders.get("O999") is None


def test_list_orders_by_customer_most_recent_first(repos):
    assert [o.order_id for o in repos.orders.list_by_customer("C1")] == ["O2", "O1"]


def test_list_orders_customer_without_orders(repos):
    assert repos.orders.list_by_customer("C999") == []


def test_find_by_tracking_code_ignores_case(repos):
    assert repos.orders.find_by_tracking_code(" br9a8b7c6d5br ").order_id == "O3"
    assert repos.orders.find_by_tracking_code("BR000000000BR") is None


def test_order_without_tracking_code(repos):
    assert repos.orders.get("O2").tracking_code is None


def test_get_items(repos):
    assert [(i.product_id, i.quantity) for i in repos.orders.get_items("O1")] == [("P1", 1)]
    assert repos.orders.get_items("O999") == []


def test_find_customer_by_email_ignores_case(repos):
    assert repos.customers.find_by_email(" ANA@example.com ").customer_id == "C1"
    assert repos.customers.find_by_email("x@y.com") is None


def test_find_customer_by_phone_ignores_formatting(repos):
    assert repos.customers.find_by_phone("67 99999-1234").customer_id == "C1"
    assert repos.customers.find_by_phone("(67) 98888-7777").customer_id == "C2"
    assert repos.customers.find_by_phone("") is None
