echo -n "Enter phone: "
read phone

echo -n "Enter stock_id: "
read stock_id

echo -n "Enter airport_id: "
read airport_id

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd Test
$DIR/env/bin/python  check_stocks.py -s $stock_id -p $phone -a $airport_id
cd ..