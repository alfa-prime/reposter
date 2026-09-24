FROM postgres:17-alpine

RUN apk add --no-cache bash restic tzdata

COPY backup/entrypoint.sh /usr/local/bin/reposter-backup

ENTRYPOINT ["/usr/local/bin/reposter-backup"]
CMD ["backup"]
