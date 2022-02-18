package buildjwks;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.KeyUse;
import com.nimbusds.jose.jwk.RSAKey;
import org.apache.commons.io.FileUtils;
import org.json.*;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.security.KeyFactory;
import java.security.NoSuchAlgorithmException;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;

public class BuildJwks {
    public static void main(String[] args) throws NoSuchAlgorithmException, InvalidKeySpecException, IOException {
        
        String publicKeyContent = FileUtils.readFileToString(new File(args[0]), "UTF-8")
                .replace("-----BEGIN PUBLIC KEY-----","")
                .replace("-----END PUBLIC KEY-----","")
                .replaceAll("\n","");
        KeyFactory kf = KeyFactory.getInstance("RSA");
        X509EncodedKeySpec keySpecX509 = new X509EncodedKeySpec(Base64.getDecoder().decode(publicKeyContent));
        RSAPublicKey pubKey = (RSAPublicKey) kf.generatePublic(keySpecX509);
        RSAKey.Builder builder = new RSAKey.Builder(pubKey)
                .keyUse(KeyUse.SIGNATURE)
                .algorithm(JWSAlgorithm.RS256)
                .keyID("hub-spid-login-test");
        JWKSet jwkset = new JWKSet(builder.build());
        JSONObject json = new JSONObject(jwkset.toJSONObject());
        System.out.println( json.toString(2) );
        
        Files.write( Paths.get( args[1] ), json.toString(2).getBytes() );
    }
}