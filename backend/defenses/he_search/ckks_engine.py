"""TenSEAL CKKS engine wrapper for the Cloud RAG Security Demo.

This module wraps Microsoft SEAL's CKKS scheme (via the TenSEAL Python
bindings) into a small, demo-focused interface that:

* builds a CKKS context with the parameters defined in
  `backend.config.settings` (poly modulus degree, coefficient modulus
  bit sizes, global scale);
* generates the Galois and relinearisation keys required for encrypted
  rotations and ciphertext-ciphertext multiplications (encrypted dot
  product depends on both);
* exposes helpers to encrypt a plaintext vector, compute an encrypted
  dot product between two ciphertexts, and decrypt scalars / vectors;
* offers `export_public_context()` which serialises the context with
  the secret key stripped — useful for shipping a "server side" view of
  the context to the frontend / a remote evaluator.

Lazy-import strategy
--------------------
`tenseal` is imported lazily *inside* methods rather than at module
top-level. The native SEAL backend is being source-built separately and
may not yet be installed when this module is first imported by the
broader backend (e.g. during test collection, `--help`, or when other
defences run without HE). Deferring the import keeps this module
importable in all environments and surfaces a clear `ImportError` only
when an HE feature is actually exercised.

Singleton
---------
`get_engine()` returns a process-wide `CKKSEngine` instance, populated
on first call. CKKS key generation is expensive enough that demo
endpoints should not re-do it per request; sharing one engine matches
the spec requirement that "所有 embedding 在 seed 階段預先加密".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.config.settings import get_settings

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    import tenseal as ts


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------
@dataclass
class HEContext:
    """Serialised, secret-key-stripped view of a CKKS context.

    The `serialized` bytes are produced by `Context.serialize(save_secret_key=False)`
    so they can be transmitted to a party that should only *evaluate*
    (compute encrypted dot products) without being able to decrypt.

    Attributes:
        serialized: The raw bytes of the public context.
    """

    serialized: bytes


# ---------------------------------------------------------------------------
# CKKSEngine
# ---------------------------------------------------------------------------
class CKKSEngine:
    """Thin wrapper around a TenSEAL CKKS context.

    The engine owns one TenSEAL `Context` plus the Galois and
    relinearisation keys required for encrypted dot products. All
    plaintext / ciphertext interaction with TenSEAL goes through this
    object so the rest of the codebase never has to call `tenseal`
    directly.

    Attributes:
        poly_modulus_degree: CKKS ring dimension (e.g. 8192).
        coeff_mod_bit_sizes: Bit-sizes of the coefficient-modulus primes.
            The first and last entries are reserved for the special
            "high-end" primes; the middle entries determine the
            multiplicative depth.
        global_scale: The CKKS scale (typically 2 ** 40) used to encode
            plaintexts and to interpret ciphertext magnitudes.
    """

    def __init__(
        self,
        poly_modulus_degree: int | None = None,
        coeff_mod_bit_sizes: list[int] | None = None,
        global_scale: float | None = None,
    ) -> None:
        """Build the CKKS context and generate evaluation keys.

        Any constructor argument left as `None` is filled in from the
        application settings (`CKKS_POLY_MODULUS_DEGREE`,
        `CKKS_COEFF_MOD_BIT_SIZES`, `CKKS_GLOBAL_SCALE`). The TenSEAL
        import happens here, not at module import time, so this module
        is safe to import even when TenSEAL is not yet installed.

        Args:
            poly_modulus_degree: CKKS ring dimension. Must be a
                power of two supported by SEAL (1024, 2048, 4096,
                8192, 16384, 32768). Defaults to settings value.
            coeff_mod_bit_sizes: List of bit-sizes for the
                coefficient-modulus primes. Defaults to settings value.
            global_scale: The CKKS encoding scale. Defaults to
                settings value.

        Raises:
            ImportError: If TenSEAL is not installed in the current
                environment.
        """
        # Lazy import — see module docstring for rationale.
        import tenseal as ts  # type: ignore[import-not-found]

        settings = get_settings()
        self.poly_modulus_degree: int = (
            poly_modulus_degree
            if poly_modulus_degree is not None
            else settings.CKKS_POLY_MODULUS_DEGREE
        )
        self.coeff_mod_bit_sizes: list[int] = (
            list(coeff_mod_bit_sizes)
            if coeff_mod_bit_sizes is not None
            else list(settings.CKKS_COEFF_MOD_BIT_SIZES)
        )
        self.global_scale: float = (
            float(global_scale)
            if global_scale is not None
            else float(settings.CKKS_GLOBAL_SCALE)
        )

        # Build the CKKS context. The `scheme` argument is passed as
        # the enum `ts.SCHEME_TYPE.CKKS`, matching the public TenSEAL
        # API.
        self._context: Any = ts.context(
            scheme=ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=self.poly_modulus_degree,
            coeff_mod_bit_sizes=self.coeff_mod_bit_sizes,
        )
        self._context.global_scale = self.global_scale

        # Galois keys are needed for ciphertext rotations, which TenSEAL
        # uses under the hood for `dot`. Relin keys are needed after
        # ciphertext-ciphertext multiplication to keep ciphertext size
        # constant. Generating both keeps the engine fully featured.
        self._context.generate_galois_keys()
        self._context.generate_relin_keys()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def context(self) -> Any:
        """Return the underlying TenSEAL `Context`.

        Returns:
            The TenSEAL context object. Other modules (encrypted store,
            encrypted search) need this to construct ciphertexts that
            are compatible with this engine.
        """
        return self._context

    # ------------------------------------------------------------------
    # Encryption / decryption helpers
    # ------------------------------------------------------------------
    def encrypt_vector(self, plaintext_vector: list[float]) -> Any:
        """Encrypt a real-valued vector as a single CKKS ciphertext.

        Args:
            plaintext_vector: The plaintext numbers to encrypt. CKKS
                packs all slots into one ciphertext, so a 768-dim
                embedding fits in a single ciphertext as long as the
                ring dimension is large enough (8192 supports up to
                4096 slots, which is sufficient for gtr-t5-base).

        Returns:
            A TenSEAL `CKKSVector` ciphertext. The concrete type is
            returned as `Any` to keep this module importable without
            TenSEAL installed.
        """
        import tenseal as ts  # type: ignore[import-not-found]

        # Defensive copy + cast to float so callers can pass numpy
        # arrays, tuples, or generators without surprises.
        as_floats = [float(x) for x in plaintext_vector]
        return ts.ckks_vector(self._context, as_floats)

    def encrypted_dot_product(self, enc_v1: Any, enc_v2: Any) -> Any:
        """Compute the encrypted dot product of two CKKS ciphertexts.

        Both inputs must have been encrypted with this engine's
        context. TenSEAL's `CKKSVector.dot` produces a ciphertext whose
        first slot contains the inner product; subsequent slots hold
        intermediate rotation artefacts and should be ignored.

        Args:
            enc_v1: The first encrypted vector.
            enc_v2: The second encrypted vector.

        Returns:
            A `CKKSVector` ciphertext whose slot-0 decrypts to the
            real-valued dot product (up to CKKS approximation error).
        """
        return enc_v1.dot(enc_v2)

    def decrypt_scalar(self, enc_scalar: Any) -> float:
        """Decrypt a ciphertext and return its first slot as a float.

        Useful for ciphertexts produced by `encrypted_dot_product`,
        where the meaningful value sits in slot 0.

        Args:
            enc_scalar: An encrypted CKKS vector whose first slot
                represents the desired scalar.

        Returns:
            The plaintext scalar as a Python float. CKKS is an
            approximate scheme, so this value typically differs from
            the ideal real-number result by a small numerical error
            governed by the global scale.
        """
        decrypted = enc_scalar.decrypt()
        if not decrypted:
            return 0.0
        return float(decrypted[0])

    def decrypt_vector(self, enc_vec: Any) -> list[float]:
        """Decrypt a full CKKS vector into a Python list of floats.

        Args:
            enc_vec: An encrypted CKKS vector.

        Returns:
            The decrypted slots as a `list[float]`. Note that CKKS
            packs the entire ring with slots, so the returned list may
            be longer than the original plaintext if the encoder padded
            it; callers that care about the original length should
            slice the result themselves.
        """
        decrypted = enc_vec.decrypt()
        return [float(x) for x in decrypted]

    # ------------------------------------------------------------------
    # Public context export
    # ------------------------------------------------------------------
    def export_public_context(self) -> HEContext:
        """Serialise the context *without* the secret key.

        The returned `HEContext` is safe to share with an evaluator
        (e.g. a "cloud" component in the demo) that must perform
        encrypted dot products but should never be able to decrypt.

        Returns:
            An `HEContext` wrapping the serialised public context
            bytes.
        """
        serialized = self._context.serialize(save_secret_key=False)
        # TenSEAL returns `bytes` already, but cast defensively in case
        # a future version returns `bytearray` or similar.
        return HEContext(serialized=bytes(serialized))


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_engine_singleton: CKKSEngine | None = None


def get_engine() -> CKKSEngine:
    """Return a process-wide singleton `CKKSEngine`.

    The first call constructs the engine (which performs the costly
    CKKS key generation); subsequent calls return the same instance.
    The singleton is intentionally implemented as a module-level
    variable rather than `functools.lru_cache`, so tests can reset it
    by clearing `_engine_singleton` if they need a fresh engine.

    Returns:
        The shared `CKKSEngine` instance.
    """
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = CKKSEngine()
    return _engine_singleton


__all__: list[str] = ["HEContext", "CKKSEngine", "get_engine"]
