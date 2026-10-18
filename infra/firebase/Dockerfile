# Firebase Auth Emulator for development and tests (no Google account needed).
# "demo-*" project IDs never contact real Firebase services.
FROM node:22-alpine
RUN npm install -g firebase-tools@14 >/dev/null 2>&1 \
 && addgroup -S firebase && adduser -S -G firebase firebase
WORKDIR /srv/firebase
COPY --chown=firebase:firebase firebase.json .firebaserc ./
USER firebase
EXPOSE 9099
HEALTHCHECK --interval=5s --timeout=3s --retries=30 \
  CMD wget -qO- http://127.0.0.1:9099/ > /dev/null || exit 1
CMD ["firebase", "emulators:start", "--only", "auth", "--project", "demo-delphin"]
