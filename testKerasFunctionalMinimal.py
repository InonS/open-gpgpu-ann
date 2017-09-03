from logging import DEBUG, basicConfig, debug
from sys import stdout

from keras.activations import relu, softmax
from keras.backend import categorical_crossentropy, expand_dims, one_hot
from keras.datasets.mnist import load_data
from keras.engine import Model
from keras.layers import Conv2D, Dense, Input
from keras.metrics import categorical_accuracy

SAME = 'SAME'


def image_input(img_width=1 << 8, img_height=1 << 8, n_channels=3):
    """
    :param img_width:
    :param img_height:
    :param n_channels:  e.g. Monochrome = 1, RGB = 3, Hyperspectral > 1, etc.
    :return:
    """
    return Input(shape=(img_width, img_height, n_channels))


def conv2d_of(window_length, n_conv_filters=int(1 << 6)):
    return Conv2D(n_conv_filters, (window_length, window_length), padding=SAME, activation=relu)


def conv_tower(window_length, input_img):
    first_layer = conv2d_of(1)(input_img)
    return conv2d_of(window_length)(first_layer)


def preprocess(train_dataset, test_dataset, n_classes_expected):
    (x_train, y_train), (x_test, y_test) = train_dataset, test_dataset
    debug("x_train[0].shape = {}, y_train[0].shape = {}".format(x_train[0].shape, y_train[0].shape))

    y_train = one_hot(y_train, n_classes_expected)
    y_test = one_hot(y_test, n_classes_expected)

    x_train = expand_dims(x_train) if len(x_train[0].shape) == 2 else x_train  # add n_channels = 1 if missing
    img_width, img_heigth, n_channels = x_train[0].shape
    return (img_width, img_heigth, n_channels), y_train, y_test


def run():
    (x_train, y_train), (x_test, y_test) = load_data()

    n_classes_expected = 10
    (img_width, img_heigth, n_channels), y_train, y_test = \
        preprocess((x_train, y_train), (x_test, y_test), n_classes_expected)

    input_img = image_input(img_width=img_width, img_height=img_heigth, n_channels=n_channels)
    cnn = conv_tower(3, input_img)
    predictions = Dense(n_classes_expected, activation=softmax)(cnn)

    model = Model(inputs=input_img, outputs=predictions, name="inception")
    model.compile(optimizer='rmsprop', loss=categorical_crossentropy, metrics=[categorical_accuracy])

    model.fit(x_train, y_train, batch_size=None, epochs=1, validation_split=0.3)
    model.evaluate(x_test, y_test, batch_size=None)


def main():
    basicConfig(level=DEBUG, stream=stdout)
    run()


if __name__ == '__main__':
    main()
