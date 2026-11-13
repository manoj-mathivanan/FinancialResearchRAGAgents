# Match the Alpine PostgreSQL base of the existing Trader cluster.
ARG POSTGRES_IMAGE=postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
FROM ${POSTGRES_IMAGE} AS build
RUN apk add --no-cache build-base
COPY pgvector.tar.gz /tmp/
RUN echo 'cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85  /tmp/pgvector.tar.gz' | sha256sum -c \
    && mkdir /tmp/pgvector \
    && tar -xzf /tmp/pgvector.tar.gz --strip-components=1 -C /tmp/pgvector \
    && cd /tmp/pgvector \
    && make -j1 OPTFLAGS="" with_llvm=no \
    && make install DESTDIR=/tmp/install OPTFLAGS="" with_llvm=no

FROM ${POSTGRES_IMAGE}
COPY --from=build /tmp/install/ /
