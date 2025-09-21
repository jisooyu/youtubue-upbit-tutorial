def paid_fee_pct (volume, price, paid_fee):
    percentage = paid_fee/(price * volume) * 100
    return percentage

vol1 = 0.10955552
p1 = 160000000
paid_fee1 = 8764.4416

result1 = paid_fee_pct(vol1, p1, paid_fee1)
print (f"Paid Fee Percentage of Upbit is {result1:.2f}%")

vol2 = 0.04506786
p2 = 160431000
paid_fee2 = 3615.14092383
result2 = paid_fee_pct(vol2, p2, paid_fee2)
print (f"Paid Fee Percentage of Upbit is {result2:.2f}%")