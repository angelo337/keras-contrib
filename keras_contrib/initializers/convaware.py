from __future__ import absolute_import
from keras import backend as K
from keras.initializers import *
from keras.initializers import _compute_fans


class ConvolutionAware(Initializer):
    """
    Initializer that generates orthogonal convolution filters in the fourier
    space. If this initializer is passed a shape that is not 3D or 4D,
    orthogonal initialization will be used.
    # Arguments
        eps_std: Standard deviation for the random normal noise used to break
        symmetry in the inverse fourier transform.
        seed: A Python integer. Used to seed the random generator.
    # References
        Armen Aghajanyan, https://arxiv.org/abs/1702.06295
    """

    def __init__(self, eps_std=0.05, seed=None):
        self.eps_std = eps_std
        self.seed = seed
        self.orthogonal = Orthogonal()

    def __call__(self, shape):
        rank = len(shape)

        if self.seed is not None:
            np.random.seed(self.seed)

        fan_in, fan_out = _compute_fans(shape, K.image_data_format())
        variance = 2 / fan_in

        if rank == 3:
            row, stack_size, filters_size = shape

            transpose_dimensions = (2, 1, 0)
            kernel_shape = (row,)
            correct_ifft = lambda shape, s=[None]: np.fft.irfft(shape, s[0])
            correct_fft = np.fft.rfft

        elif rank == 4:
            row, column, stack_size, filters_size = shape

            transpose_dimensions = (2, 3, 0, 1)
            kernel_shape = (row, column)
            correct_ifft = np.fft.irfft2
            correct_fft = np.fft.rfft2

        elif rank == 5:
            x, y, z, stack_size, filters_size = shape

            transpose_dimensions = (3, 4, 0, 1, 2)
            kernel_shape = (x, y, z)
            correct_fft = np.fft.rfftn
            correct_ifft = np.fft.irfftn
        else:
            return K.variable(self.orthogonal(shape), dtype=K.floatx())

        kernel_fourier_shape = correct_fft(np.zeros(kernel_shape)).shape

        init = []
        for i in range(filters_size):
            basis = self._create_basis(
                stack_size, np.prod(kernel_fourier_shape))
            basis = basis.reshape((stack_size,) + kernel_fourier_shape)

            filters = [correct_ifft(x, kernel_shape) +
                       np.random.normal(0, self.eps_std, kernel_shape) for
                       x in basis]

            init.append(filters)

        # Format of array is now: filters, stack, row, column
        init = np.array(init)
        init = self._scale_filters(init, variance)
        return init.transpose(transpose_dimensions)

    def _create_basis(self, filters, size):
        if size == 1:
            return np.random.normal(0.0, self.eps_std, (filters, size))

        nbb = filters // size + 1
        li = []
        for i in range(nbb):
            a = np.random.normal(0.0, 1.0, (size, size))
            a = self._symmetrize(a)
            u, _, v = np.linalg.svd(a)
            li.extend(u.T.tolist())
        p = np.array(li[:filters], dtype=K.floatx())
        return p

    def _symmetrize(self, a):
        return a + a.T - np.diag(a.diagonal())

    def _scale_filters(self, filters, variance):
        c_var = np.var(filters)
        p = np.sqrt(variance / c_var)
        return filters * p

    def get_config(self):
        return {
            'eps_std': self.eps_std,
            'seed': self.seed
        }
