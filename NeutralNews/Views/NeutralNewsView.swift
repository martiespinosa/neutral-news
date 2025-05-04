//
//  NeutralNewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 13/4/25.
//

import SwiftUI
import UIKit

struct NeutralNewsView: View {
    let news: NeutralNews
    let relatedNews: [News]
    var namespace: Namespace.ID
    
    @State private var dominantColor: Color = .gray
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
//                LinearGradient(colors: [dominantColor, dominantColor.opacity(0.3), .clear], startPoint: .top, endPoint: .bottom)
//                    .ignoresSafeArea()
                
                dominantColor
                    .ignoresSafeArea()
                
                ScrollView {
                    VStack {
                        VStack(alignment: .leading, spacing: 16) {
                            HStack {
//                                Label("Noticia neutral", systemImage: "sparkles")
//                                Spacer()
                                Text(news.category.uppercased())
                                Spacer()
                                Text(news.createdAt.formatted(.dateTime.day().month(.wide).hour().minute()).uppercased())
                            }
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            
                            Text(news.neutralTitle)
                                .font(.title)
                                .fontWeight(.semibold)
                                .fontDesign(.serif)
                            
                            AsyncImage(url: URL(string: news.imageUrl ?? "")) { phase in
                                VStack(alignment: .leading, spacing: 4) {
                                    switch phase {
                                    case .empty:
                                        ShimmerView()
                                            .frame(height: 250)
                                            .clipShape(.rect(cornerRadius: 16))
                                    case .success(let image):
                                        VStack(alignment: .leading) {
                                            image
                                                .resizable()
                                                .scaledToFit()
                                                .clipShape(.rect(cornerRadius: 16))
                                            
                                            // TODO: Quitar el opcional cuando todas lo tengan
                                            if let media = Media.from(news.imageMedium ?? "") {
                                                Text("Imagen extraída de \(media.pressMedia.name), ver su noticia al final de la página.")
                                                    .font(.footnote)
                                                    .foregroundColor(.secondary)
                                            }
                                        }
                                    case .failure:
                                        Image(systemName: "photo")
                                            .font(.largeTitle)
                                            .foregroundColor(.gray)
                                            .frame(height: 250)
                                            .clipShape(.rect(cornerRadius: 16))
                                    @unknown default:
                                        EmptyView()
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity)
                            
                            Text(news.neutralDescription)
//                                .fontDesign(.serif)
                        }
                        .padding()
                        
                        Spacer()
                        
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack {
                                ForEach(relatedNews) { new in
                                    NavigationLink {
                                        NewsView(news: new, relatedNews: relatedNews, namespace: namespace)
                                            .navigationTransition(.zoom(sourceID: new.id, in: namespace))
                                    } label: {
                                        MediaHeadlineView(news: new)
                                            .matchedTransitionSource(id: new.id, in: namespace)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.leading, 16)
                        }
                    }
                    .frame(minHeight: geometry.size.height)
                    .task {
                        dominantColor = await getDominantColor(from: news.imageUrl)
                    }
                }
            }
            .scrollBounceBehavior(.basedOnSize)
            .scrollIndicators(.hidden)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    // TODO: Cambiar el link a Neutral News
                    ShareLink(item: URL(string: "https://www.apple.com")!) {
                        Label("Compartir", systemImage: "square.and.arrow.up")
                    }

                }
            }
        }
    }
}

#Preview {
    let namespace = Namespace().wrappedValue
    return NeutralNewsView(news: .mock, relatedNews: [.mock, .mock, .mock], namespace: namespace)
}
