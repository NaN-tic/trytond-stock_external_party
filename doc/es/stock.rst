#:inside:stock/stock:bullet_list:product-quantity#


* **Producto por tercero**: Permite consultar la cantidad disponible de
  un producto en función del tercero que es propetario.


#:before:stock/stock:paragraph:product-quantity#


El listado de producto por tercero lo podremos abrir desde la opción
|menu_product_form|, seleccionando el producto del que queremos saber las
cantidades, y abriendo la opción **Producto por tercero** que encontraremos
en la Flecha verde de la barra de acciones. Hay que tener en cuenta que las
cantidades positivas representan que el producto es propiedad del tercero y
lo tenemos en nuestro almacén y las cantidades negativas representan que
nuestros productos estan en el almacén del tercero.

.. |menu_product_form| tryref:: product.menu_product/complete_name


#:after:stock/stock:section:mover-mercaderia-entre-ubicaciones#


Envío/Recepción de mercaderia de terceros
=========================================

A veces enviamos mercadería a tercero que nos tienen que devolver, o recibimos
mercadería de terceros para su manipulación y posterior devolución. En ambos,
casos es importante tener constancia de la propiedad de las existencias para
terminar regularizando la situación y que los materiales vuelvan a los
verdaderos propietarios.

Para gestionar estos casos debemos utilizar un Albarán externo, que
encontraremos en |menu_shipment_external|, ya que así se relacionarán las
existencias con el tercero.

Un albarán externo puede estar en alguno de los siguientes estados:

* **Borrador**: Estado inicial en que se introducen los movimientos que
  vamos a enviar/recibir.
* **Esperando**: A la espera que la mercadería este disponible en la ubicación
  desde dónde la vamos a enviar.
* **Reservado**: Todos los movimientos han sido reservados para que se puedan
  enviar a la nueva ubicación.
* **Realizado**: La mercadería ha sido recibida/entregada.
* **Cancelado**: El albarán ha sido cancelado.

Los estados siguen el siguiente orden::

    Borrador > Esperando > Reservado > Realizado

Para crear un Albarán externo deberemos indicar siempre un |party|, junto con
la ubicación origen y la ubicación destino. En caso de que seleccionemos una
ubicación origen de cliente o proveedor, deberemos seleccionar una ubicación
destino interna y viceversa. En el primer caso estaremos realizando una
recepción, y en el segundo estaremos realizando una recepción. Una vez
rellenada esta información deberemos introducir los movimientos que queremos
realizar y seguir con los pasos del albarán.

.. |menu_shipment_external| tryref:: stock_external.menu_shipment_external_form/complete_name
.. |party| field:: stock.shipment.external/party

.. note:: El estado esperando solo tiene sentido cuando realizamos envíos de
    mercadería.
