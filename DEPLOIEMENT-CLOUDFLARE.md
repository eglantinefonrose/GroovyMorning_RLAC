Étape 1 : Préparation côté Cloudflare (Gratuit)
   1. Connectez-vous à votre Tableau de bord Cloudflare Zero Trust (https://one.dash.cloudflare.com/).
   2. Allez dans Networks > Tunnels et cliquez sur Create a tunnel.
   3. Nommez-le (ex: groovy-test) et enregistrez-le.
   4. Dans l'onglet Install connector, copiez le Token (la longue chaîne de caractères après --token).
   5. Dans l'onglet Public Hostname :
       * Subdomain : morning
       * Domain : Choisissez un domaine que vous possédez chez Cloudflare.
       * Service Type : HTTP
       * URL : java-backend:8000 (C'est le nom du service dans votre docker-compose.yml).

  Étape 2 : Lancement du serveur (Sur votre machine)
   1. Configurez le jeton : Créez le fichier .env à la racine de votre projet :

   1     echo "TUNNEL_TOKEN=VOTRE_TOKEN_COPIÉ_PRÉCÉDEMMENT" > .env
   2. Démarrez tout avec Docker :

   1     docker-compose up -d --build
   3. Vérifiez sur le dashboard Cloudflare que le tunnel passe au statut HEALTHY (en vert).

  Étape 3 : Configuration dans le simulateur Android
   1. Lancez votre application dans le simulateur Android Studio.
   2. Allez dans les Réglages (icône engrenage en haut à droite).
   3. Désactivez le "Mode Simulation" (car vous allez maintenant taper sur votre vrai serveur distant).
   4. Dans le champ Adresse IP, saisissez votre URL publique complète :
       * https://morning.votre-domaine.com (utilisez bien https).
   5. Cliquez sur Enregistrer/Terminer.

  Étape 4 : Validation du test
   1. Synchronisation : L'application devrait charger les chroniques. Si vous regardez les logs Android (Logcat), vous devriez voir que l'app
      appelle désormais https://morning.votre-domaine.com/api/getUserChronicles.
   2. Vérification Backend : Sur votre machine, vérifiez les logs Docker :
   1     docker logs -f rlac-java-backend
      Vous devriez voir les requêtes arriver depuis l'adresse IP de Cloudflare.
   3. Le test ultime : Coupez le Wi-Fi de votre ordinateur (si le simulateur utilise le réseau de l'hôte) ou essayez depuis votre vrai
      téléphone en 4G. Si les chroniques s'affichent, votre déploiement "Cloud Personnel" est opérationnel !

  Pourquoi tester via le tunnel est important ?
   * HTTPS : Cela valide que l'application gère correctement les connexions sécurisées.
   * Performance : Vous verrez s'il y a de la latence lors de la récupération des fichiers audio (m3u8).
   * Stabilité : Cela confirme que le lien entre le Backend Java et le Segmenter Python fonctionne bien à travers le réseau Docker
     (http://python-segmenter:8001).
